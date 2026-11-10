# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Embeddings computation: one vector per medium, for the media types a job chooses.

A record may hold several media — nuScenes has six camera images — and each gets its own vector,
stored with the record and the view it belongs to, so a search finds a medium and returns its
record.

The first real job kind. It serves as the reference for the next ones — pre-annotation, video
tracking — because it exercises everything they will: reading a dataset, designating media
without moving bytes around when that can be avoided, calling the inference in batches, telling
a transient failure from a definitive one, and writing a result that replaying does not
duplicate.
"""

import logging
import time
from typing import Any, Iterable

import httpx
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_inference.schemas import EmbeddingRequest
from pydantic import Field

from pixano.datasets.embedding_spaces import AmbiguousModelError
from pixano.inference.types import TASK_TO_CAPABILITY, InferenceTask

from ..reader import JobReader, MediaType
from ..writer import JobWriter, ModelIdentity
from .base import (
    CONFIRM_MARKER,
    MODEL_TASK_MARKER,
    Chunk,
    JobKind,
    JobParams,
    Outcome,
    QuarantinedItem,
    TransientError,
    media_chunks,
)
from .inference import (
    REFUSED_BY_THE_SERVER,
    InferenceServer,
    blame_the_server_or_the_media,
    chunk_media,
    classify,
    quarantined_item,
    refusal_detail,
    transient_reason,
)


log = logging.getLogger("pixano-worker")

# The task of the model this kind calls, in Pixano's vocabulary — the one the form sends to the
# application to list the served models — and the same task in pixano-inference's, which the
# worker asks the server about. The two differ for some tasks (segmentation), hence one source.
EMBEDDING_TASK = InferenceTask.EMBEDDING
EMBEDDING_CAPABILITY = TASK_TO_CAPABILITY[EMBEDDING_TASK]

# Why a job refuses a dataset whose embeddings.json it could not read entirely: rewritten, the
# description would lose what this build left out, and the vectors it names.
UNREADABLE_EMBEDDINGS = (
    "this dataset's description of its embeddings (embeddings.json) cannot be read entirely, so no job may "
    "change it: submit the job again if it was a passing error; if it stays so, repair the file, or compute "
    "every model's embeddings again from nothing from the explorer"
)


class EmbeddingsParams(JobParams):
    """Parameters of the embeddings computation.

    Attributes:
        model: The model name as the inference declares it.
        media: The media types to embed. A record may hold several — nuScenes has six camera
            images and a point cloud — and each medium gets its own vector. A type this kind
            cannot send to the inference refuses the whole job.
        replace_existing_embeddings: Delete the vectors this model — this checkpoint of it —
            already computed on the dataset before computing them again; the other models' are
            left as they are. Without it, the job adds to its model's vectors, replacing those of
            the media it embeds again. Done once, at planning; the form asks for confirmation.
        chunk_size: Media per chunk. It is also the size of the batch sent to the
            inference: one chunk is one call. The default of 8 is measured, not assumed —
            see "Chunk size, measured" in docs/specs/backend-processing.md. On CPU, growing
            the batch slows the job down instead of speeding it up, and a small chunk also
            reduces what a resumption has to redo. On GPU the trade-off will probably flip:
            that is precisely why this parameter exists.
        normalize: Normalise the vectors, so that cosine similarity is a dot product.
        max_retries: Short retries of a call that failed transiently, done by the inference
            client before handing back. Beyond that, the chunk is handed back to the queue,
            which will replay it later.
        request_timeout_s: Beyond this, the call is considered lost. Generous, because a model
            on CPU takes time and giving up too early would turn slowness into failure.
    """

    # No default: the model is whichever the inference serves for embeddings, which the form
    # offers; a name written here would be a guess about a deployment.
    model: str = Field(min_length=1, json_schema_extra={MODEL_TASK_MARKER: EMBEDDING_TASK.value})
    # A plain default rather than a factory: pydantic publishes it in the JSON schema, and the
    # submission form starts from it — with a factory the form started with nothing ticked.
    # Pydantic copies a mutable default, so no instance shares the list.
    media: list[MediaType] = Field(default=["image"], min_length=1)
    replace_existing_embeddings: bool = Field(
        default=False,
        json_schema_extra={
            CONFIRM_MARKER: "This deletes every vector this model already computed on this dataset before "
            "computing them again. The other models' vectors are kept."
        },
    )
    chunk_size: int = Field(default=8, ge=1, le=256)
    normalize: bool = True
    max_retries: int = Field(default=3, ge=0, le=10)
    request_timeout_s: float = Field(default=300.0, gt=0)


class EmbeddingsKind(JobKind[EmbeddingsParams]):
    """Computes one vector per medium and writes it into the dataset."""

    name = "embeddings"
    params_model = EmbeddingsParams
    # The inference's embedding endpoint takes images or text; this kind sends images.
    supported_media = frozenset({"image"})
    # An embedding is indeed the output of a model.
    source_type = "model"

    def __init__(self, inference_url: str = "", api_key: str = "") -> None:
        """Bind this kind to the inference server the worker knows."""
        self.server = InferenceServer(inference_url, api_key)

    #: How the engine runs the job, not what it computes: absent from the provenance.
    params_not_in_provenance = JobKind.params_not_in_provenance | {
        "request_timeout_s",
        "max_retries",
        # What the job did to the dataset before computing, not how a vector was computed.
        "replace_existing_embeddings",
    }

    def model_identity(self, params: EmbeddingsParams) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it.

        Embedding rows carry no provenance: the model and its checkpoint name the dataset's
        embeddings space they go to, and complete the job's own provenance.
        """
        return self.server.model_identity(params.model)

    @staticmethod
    def _checkpoint_written(result: dict[str, Any], payload: dict[str, Any]) -> str:
        """The checkpoint a chunk's vectors are written under: the weights that answered, else planning's."""
        answered, planned = result.get("checkpoint") or "", payload.get("checkpoint") or ""
        if answered and planned and answered != planned:
            log.warning(
                "the inference serves the model with %s, not the %s it served when the job was planned: "
                "these vectors go to its own space",
                answered,
                planned,
            )
        return answered or planned

    @staticmethod
    def _checkpoint_of(writer: JobWriter) -> str:
        """The checkpoint of the writer's model, asked outside the dataset's lock; empty if untold."""
        return (writer.model.version if writer.model is not None else None) or ""

    def prepare(self, writer: JobWriter, params: EmbeddingsParams) -> None:
        """Empty the vectors of the job's model first, when the job was asked to replace them.

        Its space stays where it is, the default one if it was. Idempotent — a model the dataset
        holds no vectors of is left as it is — and destructive only on the explicit parameter, as
        the contract requires. The model's checkpoint is the one the writer's model was asked for,
        right after planning: a checkpoint the inference does not tell empties only a space
        recorded without one, and refuses the job rather than empty another weights' vectors.

        Raises:
            ValueError: Which of the model's spaces is this job's cannot be told.
        """
        if not params.replace_existing_embeddings:
            return
        checkpoint = self._checkpoint_of(writer)
        try:
            writer.empty_embeddings(params.model, checkpoint)
        except AmbiguousModelError as error:
            advice = (
                "delete those of its embeddings that are not this checkpoint's first"
                if checkpoint
                else "the inference does not say which weights it serves: submit the job again once it does"
            )
            raise ValueError(f"cannot tell which of this model's embeddings to replace: {error}; {advice}") from error

    def finalize(self, reader: JobReader, writer: JobWriter, params: EmbeddingsParams) -> None:
        """Index the vectors, once the job wrote them all.

        The index is trained on the whole table, which no chunk sees: built chunk by chunk, it
        would be trained again at every write. Idempotent, since the index is rebuilt whole.

        A build that fails is tried again later rather than failing the job: the vectors are all
        written, and what fails a build is mostly another writer of the table — the
        application's own computation, a recompute, a rollback, another worker — whose commit
        conflicts with the index's. Until an index is built, the search stays exact.

        Raises:
            TransientError: The index could not be built this time.
        """
        try:
            writer.index_embeddings(params.model)
        except Exception as error:
            # Logged with its trace here: the runner logs a transient failure by its reason alone,
            # and a build that fails for good would otherwise leave only its message behind.
            log.warning("job %s: the embeddings could not be indexed, tried again later", writer.job_id, exc_info=True)
            raise TransientError(f"the embeddings could not be indexed: {error}") from error

    def plan(self, reader: JobReader, params: EmbeddingsParams) -> Iterable[Chunk]:
        """Split the chosen media into batches.

        A task is a medium, not a record: the cost of a chunk is its number of calls to the
        inference, one per medium, so batching media keeps chunks alike — a batch of nuScenes
        records would hold six images each, a batch of its lidar sweeps none. A chunk never
        mixes tables, hence media types, since two types do not go to the same model.

        The chunk carries identifiers only. The images will be read at execution — putting the
        resolved references in it would swell the chunk table by the weight of the dataset for
        datasets whose media are embedded.

        Everything that can refuse the job is checked here, before any computation: the media
        types chosen, the model being served, and the dataset's description of its embeddings,
        which no job may change unless it was read entirely. Another model's vectors are no
        reason to refuse: each model has a table of its own. Each chunk carries the model's
        checkpoint as the server tells it now.

        Raises:
            ValueError: A chosen media type cannot be processed, the inference serves no such
                model, the dataset's description of its embeddings cannot be read entirely, or the
                inference tells no checkpoint for a model the dataset holds several of.
        """
        self.refuse_unsupported_media(params.media)
        told = self.server.require_served(params.model, EMBEDDING_CAPABILITY)
        if not reader.dataset.record_embeddings_fully_read():
            raise ValueError(UNREADABLE_EMBEDDINGS)
        held = [space for space in reader.dataset.record_embedding_spaces() if space["model_id"] == params.model]
        if told == "" and len(held) > 1:
            # A server that answers without naming the weights never will: no chunk could tell
            # which of them its vectors are, and each would run its inference for nothing.
            raise ValueError(
                f"the inference does not say which weights it serves '{params.model}' with, and this dataset "
                f"holds the embeddings of {len(held)} of its checkpoints: delete those not served any more first"
            )
        # The weights the server serves now, read again: the chunks' fallback, when they cannot ask.
        checkpoint = told or ""
        for chunk in media_chunks(reader, params.media, params.chunk_size):
            yield chunk.model_copy(update={"payload": {**chunk.payload, "checkpoint": checkpoint}})

    def process(self, reader: JobReader, payload: dict[str, Any], params: EmbeddingsParams) -> dict[str, Any]:
        """Embed a batch of media and return their vectors, with the fate of each medium.

        Two outcomes per medium. A medium that cannot be found, or that the inference refuses,
        goes to **quarantine** under its own identifier, its record in the detail. Otherwise it
        is **produced**. Nothing is skipped: planning only schedules media that exist.

        Raises:
            TransientError: The inference does not answer, or refuses the whole batch through no
                fault of any image.
        """
        if "view_ids" not in payload:
            # Planned by a worker from before embeddings were per medium: its payload names
            # records. Said plainly rather than failing on a missing key.
            raise ValueError(
                "this chunk was planned by an earlier version of the embeddings job, by record; "
                "cancel the job and submit it again"
            )
        table: str = payload["table"]
        view_ids: list[str] = payload["view_ids"]
        # Timed per phase — reading the dataset, inference call, then the write in `write` —
        # because a measurement that timed only whole jobs could not say where the time went when
        # a bigger batch turned out to be slower.
        started = time.perf_counter()
        found = chunk_media(reader, table, view_ids)
        candidates = [(view.id, reference) for view, reference in found.media]
        record_of = {view.id: view.record_id for view, _ in found.media}
        read_s = time.perf_counter() - started

        # Closed with the chunk: a client holds a connection pool, and a worker runs thousands
        # of chunks.
        with self.server.client(max_retries=params.max_retries) as client:
            started = time.perf_counter()
            embedded, refused = self._embed_isolating(client, candidates, params)
            inference_s = time.perf_counter() - started
            if refused and not embedded:
                # The whole batch is refused, image by image. A broken inference refuses
                # everything; so does an entirely corrupt batch. What tells them apart is not the
                # batch size — the last chunk of a dataset often has only one image — but the
                # server itself, on an image known to be good.
                blame_the_server_or_the_media(
                    lambda reference: self._embed(client, [reference], params),
                    reader,
                    table,
                    [view_id for view_id, _ in refused],
                    found.by_path,
                )
        quarantined = found.quarantined + [
            quarantined_item(view_id, REFUSED_BY_THE_SERVER, record_of[view_id], **detail)
            for view_id, detail in refused
        ]

        return {
            "record_ids": [record_of[view_id] for view_id, _ in embedded],
            "view_ids": [view_id for view_id, _ in embedded],
            "vectors": [vector for _, vector in embedded],
            # The weights that answered, as the server tells them right after: the space the
            # vectors go to, whatever was served when the job was planned.
            "checkpoint": (self.server.served_checkpoint(params.model) or "") if embedded else "",
            "skipped": 0,
            "quarantined": quarantined,
            "carried_bytes": found.carried_bytes,
            "phases_s": {"read": read_s, "inference": inference_s},
        }

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """What `process` observed for each medium."""
        return Outcome(
            produced=len(result["vectors"]),
            skipped=result["skipped"],
            quarantined=[QuarantinedItem.model_validate(item) for item in result["quarantined"]],
        )

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: EmbeddingsParams
    ) -> None:
        """Write one vector per medium, replacing the previous one.

        The key is the medium: recomputing a dataset's embeddings replaces the vectors instead
        of stacking a second series. The model's checkpoint is the one the server told right
        after it answered (`process`), or failing it the one planning read — never one this worker
        remembers from another job. A chunk whose checkpoint is told by neither, which the dataset
        cannot place between several checkpoints of the model, is handed back rather than written
        by guess.

        Raises:
            TransientError: The checkpoint is not told, and the dataset holds several of the model's:
                a later attempt may be told it.
            ValueError: The checkpoint told matches several spaces recorded without theirs: no
                attempt will tell more.
        """
        vectors = result["vectors"]
        started = time.perf_counter()
        if vectors:
            checkpoint = self._checkpoint_written(result, payload)
            try:
                space = writer.write_media_embeddings(
                    record_ids=result["record_ids"],
                    view_ids=result["view_ids"],
                    vectors=vectors,
                    model=params.model,
                    checkpoint=checkpoint,
                )
            except AmbiguousModelError as error:
                if checkpoint:
                    raise ValueError(f"the embeddings of this chunk have no space of their own: {error}") from error
                raise TransientError(f"the embeddings of this chunk have no space to go to yet: {error}") from error
            if space is not None and not checkpoint and space["checkpoint"]:
                log.warning(
                    "job %s: the inference did not say which weights it served; the vectors go to the one space "
                    "of %s, of the checkpoint %s",
                    writer.job_id,
                    params.model,
                    space["checkpoint"],
                )
        phases = result.get("phases_s", {})
        # One line per chunk, with the job: this is what scripts/measure_throughput.py adds up.
        log.info(
            "job %s: phases read %.3f s, inference %.3f s, write %.3f s (%d vector(s), %d image(s) as bytes)",
            writer.job_id,
            phases.get("read", 0.0),
            phases.get("inference", 0.0),
            time.perf_counter() - started,
            len(vectors),
            result.get("carried_bytes", 0),
        )

    def _embed_isolating(
        self, client: SyncPixanoInferenceClient, candidates: list[tuple[str, str]], params: EmbeddingsParams
    ) -> tuple[list[tuple[str, list[float]]], list[tuple[str, dict[str, Any]]]]:
        """Embed a batch, and if it is refused, find the image or images at fault.

        The inference answers 500 for a corrupt image as well as for a missing path, and then
        refuses the whole batch: its return code does not point at the culprit. We cut the batch
        in two and start again, until the images that fail on their own are isolated. A batch of
        eight with one corrupt image costs seven calls instead of one — but only on the day an
        image is corrupt, and the seven others are saved.

        An image is only blamed on an **answer** from the server, never on its silence. A
        connection outage in the middle of the search makes the whole chunk transient: cut off
        mid-job, the inference was restarting, one call passed, the next ones found the
        connection refused — and seven healthy images went to quarantine.

        Returns:
            The vectors obtained, and the refused media with the detail of the refusal.

        Raises:
            TransientError: The inference does not answer or asks to come back later.
            PixanoInferenceError: An error that depends on no image — an unknown model, a denied
                access, an answer this worker cannot read. It is fatal to the chunk.
        """
        if not candidates:
            return [], []
        try:
            vectors = self._embed(client, [reference for _, reference in candidates], params)
        except (httpx.TransportError, PixanoInferenceError) as error:
            failure = classify(error)
            if failure == "transient":
                raise TransientError(transient_reason(error)) from error
            if failure == "request":
                raise
            # A medium is only blamed on an answer: what reaches here is the server's refusal.
            assert isinstance(error, PixanoInferenceError)
            if len(candidates) == 1:
                return [], [(candidates[0][0], refusal_detail(error))]
            middle = len(candidates) // 2
            left_ok, left_ko = self._embed_isolating(client, candidates[:middle], params)
            right_ok, right_ko = self._embed_isolating(client, candidates[middle:], params)
            return left_ok + right_ok, left_ko + right_ko
        return [(record_id, vector) for (record_id, _), vector in zip(candidates, vectors, strict=True)], []

    @staticmethod
    def _embed(
        client: SyncPixanoInferenceClient, references: list[str], params: EmbeddingsParams
    ) -> list[list[float]]:
        """One embedding call.

        The call goes through the official client rather than a hand-written HTTP request: the
        vectors travel as an encoded numpy array, and guessing that encoding again would be one
        more assumption to maintain. The client replays brief failures on its own.
        """
        request = EmbeddingRequest(model=params.model, image=references, normalize=params.normalize)
        response = client.embedding(request, timeout=params.request_timeout_s)
        return [list(vector) for vector in response.data.embeddings.to_numpy()]
