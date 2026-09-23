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

from ..reader import JobReader, MediaType
from ..writer import JobWriter, ModelIdentity, check_embedding_space
from .base import CONFIRM_MARKER, Chunk, JobKind, JobParams, Outcome, QuarantinedItem, TransientError


log = logging.getLogger("pixano-worker")

# The capability pixano-inference declares for a model this kind can call.
EMBEDDING_CAPABILITY = "embedding"

# The answers that say "come back later": timeout, too many requests, service unavailable. The
# client already replays 502, 503 and 504 on its own; what reaches this point has survived its
# retries and belongs to the queue.
TRANSIENT_STATUSES = frozenset({408, 429, 502, 503, 504})

# The answers that say "this request will never pass", whatever its content: no permission, no
# route, no model. Splitting the batch would change nothing.
REQUEST_STATUSES = frozenset({401, 403, 404, 405})

# How long a chunk may wait to learn which checkpoint the model runs. The answer only completes
# the provenance: a slow server must not hold the chunk for the client's default minute.
CHECKPOINT_QUERY_TIMEOUT_S = 5.0

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

    model: str = Field(default="clip", min_length=1)
    media: list[MediaType] = Field(default_factory=lambda: ["image"], min_length=1)
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
        self.inference_url = inference_url.rstrip("/")
        self.api_key = api_key
        self._checkpoints: dict[str, str] = {}

    #: How the engine runs the job, not what it computes: absent from the provenance.
    params_not_in_provenance = JobKind.params_not_in_provenance | {
        "request_timeout_s",
        "max_retries",
        # What the job did to the dataset before computing, not how a vector was computed.
        "replace_existing_embeddings",
    }

    def model_identity(self, params: EmbeddingsParams) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it.

        The server declares no version as such; the checkpoint path is what identifies which
        weights answered. Embedding rows carry no provenance today — the model lives in the
        dataset's sidecar as long as one table holds one model — so this is the reference
        implementation the pre-annotation kinds copy, not something the vectors record.

        Asked once per model per process, and only a successful answer is remembered: a
        server that could not be asked is asked again on the next chunk rather than leaving
        every later row without a version.
        """
        if params.model not in self._checkpoints:
            checkpoint = self._checkpoint_of(params.model)
            if checkpoint is None:
                return ModelIdentity(params.model)
            self._checkpoints[params.model] = checkpoint
        return ModelIdentity(params.model, self._checkpoints[params.model])

    def _checkpoint_of(self, model: str) -> str | None:
        try:
            with SyncPixanoInferenceClient(
                self.inference_url,
                api_key=self.api_key or None,
                max_retries=0,
                timeout=CHECKPOINT_QUERY_TIMEOUT_S,
            ) as client:
                for info in client.list_models():
                    if info.name == model:
                        return info.model_path or None
        except Exception as error:  # noqa: BLE001 — a provenance that cannot be completed must not fail the chunk
            log.warning("model '%s': cannot ask the inference for its checkpoint (%s)", model, error)
        return None

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
        self._require_served(params.model)
        check_embedding_space(reader.dataset.record_embedding_space(), params.model)
        for media_type in dict.fromkeys(params.media):
            for table in reader.media_tables(media_type):
                batch: list[str] = []
                for view_id in reader.ids(table):
                    batch.append(view_id)
                    if len(batch) == params.chunk_size:
                        yield Chunk(payload={"table": table, "view_ids": batch}, task_count=len(batch))
                        batch = []
                if batch:
                    yield Chunk(payload={"table": table, "view_ids": batch}, task_count=len(batch))

    def _require_served(self, model: str) -> None:
        """Refuse a job whose model the inference does not serve as an embedding model.

        A server that cannot be reached is not a refusal: it may be restarting, and the chunks
        will wait for it like after any outage.
        """
        try:
            with SyncPixanoInferenceClient(
                self.inference_url, api_key=self.api_key or None, max_retries=0, timeout=CHECKPOINT_QUERY_TIMEOUT_S
            ) as client:
                served = client.list_models()
        except Exception as error:  # noqa: BLE001 — an unreachable server is the chunks' concern
            log.warning("model '%s': cannot ask the inference whether it is served (%s)", model, error)
            return
        embedding = sorted(info.name for info in served if info.capability == EMBEDDING_CAPABILITY)
        if model not in embedding:
            raise ValueError(
                f"the inference serves no embedding model named '{model}' — it serves "
                f"{', '.join(embedding) or 'none'}. Deploy the model on pixano-inference, or choose one of those."
            )

    def process(self, reader: JobReader, payload: dict[str, Any], params: EmbeddingsParams) -> dict[str, Any]:
        """Embed a batch of media and return their vectors, with the fate of each medium.

        Two outcomes per medium. A medium that cannot be found, or that the inference refuses,
        goes to **quarantine** under its own identifier, its record in the detail. Otherwise it
        is **produced**. Nothing is skipped: planning only schedules media that exist.

        Raises:
            TransientError: The inference does not answer, or refuses the whole batch through no
                fault of any image.
        """
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
            self._blame_the_server_or_the_images(client, reader, table, refused, by_path, params)
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

    def _blame_the_server_or_the_images(
        self,
        client: SyncPixanoInferenceClient,
        reader: JobReader,
        table: str,
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

        first_by_path = next((view_id for view_id, _ in refused if view_id in by_path), None)
        if first_by_path is None:
            return
        found = reader.dataset.get_view_binary(table, by_path[first_by_path].id)
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
