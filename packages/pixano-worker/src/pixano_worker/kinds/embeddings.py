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
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_inference.schemas import EmbeddingRequest
from pydantic import Field

from ..reader import JobReader
from ..writer import JobWriter, ModelIdentity, check_embedding_space
from .base import Chunk, JobKind, JobParams, Outcome, QuarantinedItem, TransientError
from .inference import (
    InferenceServer,
    blame_the_server_or_the_media,
    classify,
    refusal_detail,
    transient_reason,
)


log = logging.getLogger("pixano-worker")

# The image views table, and the records table. These are Pixano's canonical names.
IMAGE_TABLE = "images"
RECORD_TABLE = "records"


class EmbeddingsParams(JobParams):
    """Parameters of the embeddings computation.

    Attributes:
        model: The model name as the inference declares it.
        chunk_size: Records per chunk. It is also the size of the batch sent to the
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

    model: str = Field(default="clip", min_length=1)
    chunk_size: int = Field(default=8, ge=1, le=256)
    normalize: bool = True
    max_retries: int = Field(default=3, ge=0, le=10)
    request_timeout_s: float = Field(default=300.0, gt=0)


class EmbeddingsKind(JobKind[EmbeddingsParams]):
    """Computes one vector per record and writes it into the dataset."""

    name = "embeddings"
    params_model = EmbeddingsParams
    # An embedding is indeed the output of a model.
    source_type = "model"

    def __init__(self, inference_url: str = "", api_key: str = "") -> None:
        """Bind this kind to the inference server the worker knows."""
        self.server = InferenceServer(inference_url, api_key)

    #: How the engine runs the job, not what it computes: absent from the provenance.
    params_not_in_provenance = JobKind.params_not_in_provenance | {"request_timeout_s", "max_retries"}

    def model_identity(self, params: EmbeddingsParams) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it.

        Embedding rows carry no provenance today — the model lives in the dataset's sidecar as
        long as one table holds one model — so this completes the job's own provenance only.
        """
        return self.server.model_identity(params.model)

    def plan(self, reader: JobReader, params: EmbeddingsParams) -> Iterable[Chunk]:
        """Split the dataset's records into batches.

        The chunk carries identifiers only. The images will be read at execution — putting the
        resolved references in it would swell the chunk table by the weight of the dataset for
        datasets whose media are embedded.

        The model is checked here, before any computation: a job that will not be able to write
        its vectors must fail at planning, not after having run the inference over the whole
        dataset.

        Raises:
            ValueError: The dataset already carries embeddings from another model.
        """
        check_embedding_space(reader.dataset.record_embedding_space(), params.model)
        batch: list[str] = []
        for record_id in reader.ids(RECORD_TABLE):
            batch.append(record_id)
            if len(batch) == params.chunk_size:
                yield Chunk(payload={"record_ids": batch}, task_count=len(batch))
                batch = []
        if batch:
            yield Chunk(payload={"record_ids": batch}, task_count=len(batch))

    def process(self, reader: JobReader, payload: dict[str, Any], params: EmbeddingsParams) -> dict[str, Any]:
        """Embed a batch of images and return their vectors, with the fate of each record.

        Three outcomes per record. Without an image view, it is **skipped**: this is not an
        error, it is a record this computation does not apply to. With an image that cannot be
        found or that the inference refuses, it goes to **quarantine**. Otherwise it is
        **produced**.

        Raises:
            TransientError: The inference does not answer, or refuses the whole batch through no
                fault of any image.
        """
        record_ids: list[str] = payload["record_ids"]
        # Timed per phase — reading the dataset, inference call, then the write in `write` —
        # because a measurement that timed only whole jobs could not say where the time went when
        # a bigger batch turned out to be slower.
        started = time.perf_counter()
        images = self._images_of(reader, record_ids) if record_ids else {}

        candidates: list[tuple[str, str]] = []
        # The images designated by path, so that one can be resent as bytes if the server refuses
        # them all while it still embeds the witness image. Not those designated by URL: the bytes
        # this worker could send say nothing of whether the inference reaches the URL's source.
        by_path: dict[str, Any] = {}
        quarantined: list[dict[str, Any]] = []
        skipped = 0
        carried = 0
        for record_id in record_ids:
            image = images.get(record_id)
            if image is None:
                skipped += 1
                continue
            resolved = reader.resolve_media(IMAGE_TABLE, image)
            if resolved is None:
                quarantined.append({"item_id": record_id, "reason": "media not found"})
                continue
            candidates.append((record_id, resolved.value))
            carried += int(resolved.carried_bytes)
            if resolved.designation == "path":
                by_path[record_id] = image

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
                    IMAGE_TABLE,
                    [record_id for record_id, _ in refused],
                    by_path,
                )
        quarantined.extend(
            {"item_id": record_id, "reason": "refused by the inference server", "detail": detail}
            for record_id, detail in refused
        )

        return {
            "record_ids": [record_id for record_id, _ in embedded],
            "vectors": [vector for _, vector in embedded],
            "skipped": skipped,
            "quarantined": quarantined,
            "carried_bytes": carried,
            "phases_s": {"read": read_s, "inference": inference_s},
        }

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """What `process` observed for each record."""
        return Outcome(
            produced=len(result["vectors"]),
            skipped=result["skipped"],
            quarantined=[QuarantinedItem.model_validate(item) for item in result["quarantined"]],
        )

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: EmbeddingsParams
    ) -> None:
        """Write one vector per record, replacing the previous one.

        The key is the record: recomputing a dataset's embeddings replaces the vectors instead
        of stacking a second series.
        """
        vectors = result["vectors"]
        started = time.perf_counter()
        if vectors:
            writer.write_record_embeddings(record_ids=result["record_ids"], vectors=vectors, model=params.model)
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

    @staticmethod
    def _images_of(reader: JobReader, record_ids: list[str]) -> dict[str, Any]:
        """The image view of each record in the batch, when it exists.

        A record may carry several image views — nuScenes has six, one per camera. This kind
        embeds **one**, the first LanceDB returns, and does not yet offer a way to choose which:
        that is a `view` parameter to add with the step 2 kinds, once we know what pre-annotation
        expects from a multi-view record.
        """
        rows = reader.dataset.get_data(IMAGE_TABLE, record_ids=list(record_ids)) or []
        by_record: dict[str, Any] = {}
        for row in rows:
            by_record.setdefault(row.record_id, row)
        return by_record

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
