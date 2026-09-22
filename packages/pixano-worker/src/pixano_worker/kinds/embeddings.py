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

import io
import logging
import time
from functools import cache
from typing import Any, Iterable

import httpx
from PIL import Image
from pixano_inference_client import EmbeddingRequest, PixanoInferenceError, SyncPixanoInferenceClient
from pydantic import Field

from pixano.inference.media import bytes_to_data_uri

from ..reader import JobReader
from ..writer import JobWriter, check_embedding_space
from .base import Chunk, JobKind, JobParams, Outcome, QuarantinedItem, TransientError


log = logging.getLogger("pixano-worker")

# The image views table, and the records table. These are Pixano's canonical names.
IMAGE_TABLE = "images"
RECORD_TABLE = "records"

# The answers that say "come back later": timeout, too many requests, service unavailable. The
# client already replays 502, 503 and 504 on its own; what reaches this point has survived its
# retries and belongs to the queue.
TRANSIENT_STATUSES = frozenset({408, 429, 502, 503, 504})

# The answers that say "this request will never pass", whatever its content: no permission, no
# route, no model. Splitting the batch would change nothing.
REQUEST_STATUSES = frozenset({401, 403, 404, 405})

# Side of the witness image: the smallest the server accepts without arguing. It only serves to
# find out whether the server can still embed anything, not to produce a vector.
WITNESS_IMAGE_SIDE = 16

# The status the client gives an error when the server answered nothing at all — connection
# refused, timeout. It wraps it in a PixanoInferenceError rather than letting the httpx error
# through.
NO_RESPONSE = 0


@cache
def witness_image() -> str:
    """A generated image, as bytes, that the server must be able to embed.

    When a whole batch is refused image by image, it tells an inference outage from a batch that
    is really corrupt: the "two refused images count as an outage" threshold it replaces made the
    decision depend on the batch size, and the last chunk of a dataset often has only one image.
    """
    image = Image.new("RGB", (WITNESS_IMAGE_SIDE, WITNESS_IMAGE_SIDE), (128, 128, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return bytes_to_data_uri(buffer.getvalue())


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
        self.inference_url = inference_url.rstrip("/")
        self.api_key = api_key

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
        # because the lot 10 measurement only dated whole jobs, and could not say where the time
        # went when a bigger batch turned out to be slower.
        started = time.perf_counter()
        images = self._images_of(reader, record_ids) if record_ids else {}

        candidates: list[tuple[str, str]] = []
        # The images sent by path, so that one can be resent as bytes if the server refuses them
        # all while it still embeds the witness image.
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
            if not resolved.carried_bytes:
                by_path[record_id] = image

        read_s = time.perf_counter() - started

        client = SyncPixanoInferenceClient(
            self.inference_url, api_key=self.api_key or None, max_retries=params.max_retries
        )
        started = time.perf_counter()
        embedded, refused = self._embed_isolating(client, candidates, params)
        inference_s = time.perf_counter() - started
        if refused and not embedded:
            # The whole batch is refused, image by image. A broken inference refuses everything;
            # so does an entirely corrupt batch. What tells them apart is not the batch size —
            # the last chunk of a dataset often has only one image — but the server itself, on an
            # image known to be good.
            self._blame_the_server_or_the_images(client, reader, refused, by_path, params)
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

    def _blame_the_server_or_the_images(
        self,
        client: SyncPixanoInferenceClient,
        reader: JobReader,
        refused: list[tuple[str, dict[str, Any]]],
        by_path: dict[str, Any],
        params: EmbeddingsParams,
    ) -> None:
        """Decide, on an entirely refused batch, whether the server or the images are to blame.

        A witness image, generated here, is sent as bytes: refused, the server is not well and
        the chunk is replayed later. Accepted, the images are at fault — unless they had been
        designated by path: the server may not read the storage it was told to mount, and then
        refuses every path through no fault of any image. So one of them is resent as bytes; if
        it passes, the mount is the cause, and the chunk is replayed with the reason, rather than
        three hundred healthy images going to quarantine.

        Raises:
            TransientError: The server refuses the witness image, or does not read its media by
                path.
        """
        try:
            self._embed(client, [witness_image()], params)
        except (httpx.TransportError, PixanoInferenceError) as error:
            raise TransientError(f"the inference refuses even the witness image: {error}") from error

        first_by_path = next((record_id for record_id, _ in refused if record_id in by_path), None)
        if first_by_path is None:
            return
        found = reader.dataset.get_view_binary(IMAGE_TABLE, by_path[first_by_path].id)
        if found is None or not found[0]:
            return
        try:
            self._embed(client, [bytes_to_data_uri(found[0])], params)
        except (httpx.TransportError, PixanoInferenceError):
            # Refused as bytes too: the image really is at fault.
            return
        raise TransientError(
            f"the inference refuses images by path but accepts the same one as bytes ({first_by_path}): "
            "it does not read the media storage — check PIXANO_INFERENCE_MEDIA_ROOT and its mount"
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
                detail = {"status": error.status_code, "code": error.code, "message": str(error.message)[:500]}
                return [], [(candidates[0][0], detail)]
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
