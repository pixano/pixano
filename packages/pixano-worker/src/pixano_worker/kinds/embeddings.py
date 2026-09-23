# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Embeddings computation: one vector per record, from its image view.

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
from pixano_inference_client import EmbeddingRequest, PixanoInferenceError, SyncPixanoInferenceClient
from pydantic import Field

from ..reader import JobReader, MediaType
from ..writer import JobWriter, ModelIdentity, check_embedding_space
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
    NO_RESPONSE,
    REQUEST_STATUSES,
    TRANSIENT_STATUSES,
    InferenceServer,
    blame_the_server_or_the_media,
    refusal_detail,
)


log = logging.getLogger("pixano-worker")

# The capability pixano-inference declares for a model this kind can call.
EMBEDDING_CAPABILITY = "embedding"


class EmbeddingsParams(JobParams):
    """Parameters of the embeddings computation.

    Attributes:
        model: The model name as the inference declares it.
        media: The media types to embed. A record may hold several — nuScenes has six camera
            images and a point cloud — and each medium gets its own vector. A type this kind
            cannot send to the inference refuses the whole job.
        replace_existing_embeddings: Delete the dataset's vectors before computing, whatever
            their model. Without it, a dataset whose vectors come from another model refuses
            the job: one table holds one model. Done once, at planning; the form asks for
            confirmation.
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
    model: str = Field(min_length=1, json_schema_extra={MODEL_TASK_MARKER: EMBEDDING_CAPABILITY})
    # A plain default rather than a factory: pydantic publishes it in the JSON schema, and the
    # submission form starts from it — with a factory the form started with nothing ticked.
    # Pydantic copies a mutable default, so no instance shares the list.
    media: list[MediaType] = Field(default=["image"], min_length=1)
    replace_existing_embeddings: bool = Field(
        default=False,
        json_schema_extra={
            CONFIRM_MARKER: "This deletes every vector already computed on this dataset, whatever their model, "
            "before computing the new ones."
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

        Embedding rows carry no provenance today — the model lives in the dataset's sidecar as
        long as one table holds one model — so this completes the job's own provenance only.
        """
        return self.server.model_identity(params.model)

    def prepare(self, writer: JobWriter, params: EmbeddingsParams) -> None:
        """Empty the embeddings table first, when the job was asked to replace it.

        Idempotent — dropping an absent table does nothing — and destructive only on the
        explicit parameter, as the contract requires.
        """
        if params.replace_existing_embeddings:
            writer.drop_embeddings()

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
        types chosen, the model being served, and the model of the vectors already there.

        Raises:
            ValueError: A chosen media type cannot be processed, the inference serves no such
                model, or the dataset already carries embeddings from another model.
        """
        self.refuse_unsupported_media(params.media)
        self.server.require_served(params.model, EMBEDDING_CAPABILITY)
        # Replacing the vectors is precisely how another model gets in: `prepare`, run once this
        # plan has succeeded, empties the table.
        if not params.replace_existing_embeddings:
            check_embedding_space(reader.dataset.record_embedding_space(), params.model)
        yield from media_chunks(reader, params.media, params.chunk_size)

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
        # because the lot 10 measurement only dated whole jobs, and could not say where the time
        # went when a bigger batch turned out to be slower.
        started = time.perf_counter()
        views = {row.id: row for row in reader.rows(table, view_ids)} if view_ids else {}

        candidates: list[tuple[str, str]] = []
        record_of: dict[str, str] = {}
        # The images sent by path, so that one can be resent as bytes if the server refuses them
        # all while it still embeds the witness image.
        by_path: dict[str, Any] = {}
        quarantined: list[dict[str, Any]] = []
        carried = 0
        for view_id in view_ids:
            view = views.get(view_id)
            if view is None:
                quarantined.append({"item_id": view_id, "reason": "media not found"})
                continue
            record_of[view_id] = view.record_id
            resolved = reader.resolve_media(table, view)
            if resolved is None:
                quarantined.append(
                    {"item_id": view_id, "reason": "media not found", "detail": {"record_id": view.record_id}}
                )
                continue
            candidates.append((view_id, resolved.value))
            carried += int(resolved.carried_bytes)
            if not resolved.carried_bytes:
                by_path[view_id] = view

        read_s = time.perf_counter() - started

        client = self.server.client(max_retries=params.max_retries)
        started = time.perf_counter()
        embedded, refused = self._embed_isolating(client, candidates, params)
        inference_s = time.perf_counter() - started
        if refused and not embedded:
            # The whole batch is refused, image by image. A broken inference refuses everything;
            # so does an entirely corrupt batch. What tells them apart is not the batch size —
            # the last chunk of a dataset often has only one image — but the server itself, on an
            # image known to be good.
            blame_the_server_or_the_media(
                lambda reference: self._embed(client, [reference], params),
                reader,
                table,
                [view_id for view_id, _ in refused],
                by_path,
            )
        quarantined.extend(
            {
                "item_id": view_id,
                "reason": "refused by the inference server",
                "detail": {**detail, "record_id": record_of[view_id]},
            }
            for view_id, detail in refused
        )

        return {
            "record_ids": [record_of[view_id] for view_id, _ in embedded],
            "view_ids": [view_id for view_id, _ in embedded],
            "vectors": [vector for _, vector in embedded],
            "skipped": 0,
            "quarantined": quarantined,
            "carried_bytes": carried,
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
        of stacking a second series.
        """
        vectors = result["vectors"]
        started = time.perf_counter()
        if vectors:
            writer.write_media_embeddings(
                record_ids=result["record_ids"], view_ids=result["view_ids"], vectors=vectors, model=params.model
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
            The vectors obtained, and the refused records with the detail of the refusal.

        Raises:
            TransientError: The inference does not answer or asks to come back later.
            PixanoInferenceError: An error that depends on no image — an unknown model, a denied
                access. It is fatal to the chunk.
        """
        if not candidates:
            return [], []
        try:
            vectors = self._embed(client, [reference for _, reference in candidates], params)
        except httpx.TransportError as error:
            raise TransientError(f"the inference does not answer: {error}") from error
        except PixanoInferenceError as error:
            if error.status_code == NO_RESPONSE:
                raise TransientError(f"the inference does not answer: {error}") from error
            if error.status_code in TRANSIENT_STATUSES:
                raise TransientError(f"the inference asks to come back later: {error}") from error
            if error.status_code in REQUEST_STATUSES:
                raise
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
