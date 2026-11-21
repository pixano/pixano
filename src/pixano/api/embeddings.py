# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Record-embedding computation job.

Computes one CLIP-style vector per record from its image view by calling the connected
pixano-inference provider, writes the vectors to the model's own embeddings space — beside the
other models', each in a table of its own —, and builds the vector index. Runs in a background
thread tracked in the shared `JobStore`, so progress is polled through the existing
``/io/jobs/{id}`` endpoint. Idempotent: records the model embedded already are skipped
(resume-safe).
"""

import logging
import os
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable, TypeVar

from pixano_inference.client import SyncPixanoInferenceClient
from pixano_inference.schemas import EmbeddingRequest

from pixano.datasets.dataset import Dataset
from pixano.datasets.io.jobs import JobSink, JobStore
from pixano.datasets.io.progress import ProgressEvent
from pixano.datasets.utils.errors import DatasetBusyError
from pixano.inference.media import bytes_to_data_uri
from pixano.inference.provider import InferenceProvider


logger = logging.getLogger(__name__)

_IMAGE_TABLE = "images"
_EMBED_BATCH = 16
# The healths of a model's space a computation goes on from without force: absent, or vectors to add to.
_COMPUTABLE = ("absent", "ready", "partial")
# How many times, and how far apart, a write is tried again while someone else writes the dataset — a
# person's save, a change of the default model, a worker's chunk.
_BUSY_ATTEMPTS = 10
_BUSY_WAIT_S = 0.5

_Written = TypeVar("_Written")


def _resolve_image_ref(dataset: Dataset, image: Any) -> str | None:
    """Resolve an image row to a value the embedding endpoint accepts (data-URI or URL).

    ``raw_bytes`` is a blob column excluded from `get_data`'s default projection, so embedded
    images are fetched via `get_view_binary`; datalake images pass their URI through.
    """
    uri = getattr(image, "uri", None)
    if uri:
        return uri
    result = dataset.get_view_binary(_IMAGE_TABLE, image.id)
    if result is not None:
        blob, _ = result
        if blob:
            return bytes_to_data_uri(blob)
    return None


def _embed_images(client: SyncPixanoInferenceClient, model: str, images: list[str]) -> list[list[float]]:
    """Embed a batch of images via the SYNCHRONOUS client.

    The compute job runs in its own thread, so it must NOT reuse the connected provider's async
    httpx client (bound to the server's event loop); a fresh sync client avoids the cross-loop hang.
    """
    response = client.embedding(EmbeddingRequest(model=model, image=images))
    return response.data.embeddings.to_numpy().tolist()


def _checkpoint_of(client: SyncPixanoInferenceClient, model: str) -> str:
    """The checkpoint the server serves the model with now; empty when it tells none.

    A model is its name and its checkpoint: untold, the space of that name is the model's if it is the
    only one (`Dataset.ensure_record_embedding_space`). Asked right after each call, as the worker does:
    the server does not say which weights answered.

    Raises:
        Exception: The server cannot be asked; a computation by name only could write another
            checkpoint's space.
    """
    return next((info.model_path or "" for info in client.list_models() if info.name == model), "")


def _past_busy(write: Callable[[], _Written]) -> _Written:
    """Make a write of the dataset, tried again while someone else writes it — each such write is short.

    Raises:
        DatasetBusyError: The dataset stayed busy past every attempt.
    """
    for attempt in range(_BUSY_ATTEMPTS):
        try:
            return write()
        except DatasetBusyError:
            if attempt == _BUSY_ATTEMPTS - 1:
                raise
            time.sleep(_BUSY_WAIT_S)
    raise AssertionError("unreachable: the last attempt returns or raises")


def _embedded_records(dataset: Dataset, space: dict[str, Any] | None) -> set[str]:
    """The records a space holds a vector of: what a resumed computation skips."""
    if space is None:
        return set()
    return {row.record_id for row in dataset.get_data(space["table"], limit=None) or []}


def _run_embedding_job(
    store: JobStore,
    job_id: str,
    dataset_path: Path,
    url: str,
    api_key: str | None,
    model: str,
    batch_size: int,
    force: bool,
) -> None:
    dataset = Dataset(dataset_path)
    client = SyncPixanoInferenceClient(url, api_key=api_key)
    store.update_job(job_id, status="running", pid=os.getpid(), heartbeat=True)
    sink = JobSink(store, job_id)
    try:
        if force and not dataset.record_embeddings_fully_read():
            # A description this build cannot read entirely: only starting again from nothing,
            # every model's embeddings deleted, repairs it.
            dataset.drop_record_embeddings()
        checkpoint = _checkpoint_of(client, model)
        space = dataset.matching_record_embedding_space(model, checkpoint)
        if space is not None and not force:
            health = dataset.record_embedding_health(space["id"])
            if health["status"] not in _COMPUTABLE:
                raise ValueError(
                    f"The embeddings of model '{model}' are broken ({health['detail']}): compute them with force."
                )
        record_ids: list[str] = dataset.get_all_ids("records")
        # Forced, the model's space is emptied with the first vectors, at their dimension: a space that
        # records another one is repaired, keeping its id, its place and the default.
        already = set() if force else _embedded_records(dataset, space)
        emptied = not force
        pending = [rid for rid in record_ids if rid not in already]
        total = len(record_ids)
        done = len(already)
        sink.emit(ProgressEvent(phase="embed", done=done, total=total, unit="records"))

        for start in range(0, len(pending), batch_size):
            if store.cancel_requested(job_id):
                store.update_job(job_id, status="cancelled")
                return
            batch_ids = pending[start : start + batch_size]
            images = dataset.get_data(_IMAGE_TABLE, record_ids=batch_ids) or []
            by_record: dict[str, Any] = {}
            for image in images:
                by_record.setdefault(image.record_id, image)

            refs: list[str] = []
            ordered_ids: list[str] = []
            for rid in batch_ids:
                image = by_record.get(rid)
                ref = _resolve_image_ref(dataset, image) if image is not None else None
                if ref is not None:
                    refs.append(ref)
                    ordered_ids.append(rid)

            if refs:
                vectors = _embed_images(client, model, refs)
                answered = _checkpoint_of(client, model)
                dim = len(vectors[0])
                if not emptied:
                    _past_busy(lambda: dataset.empty_model_record_embeddings(model, answered, dim=dim))
                    emptied = True
                # One vector per record, its first image's: that image names the row, so a vector
                # computed again replaces the one before.
                rows = [
                    {"id": by_record[rid].id, "record_id": rid, "view_id": by_record[rid].id, "vector": vector}
                    for rid, vector in zip(ordered_ids, vectors, strict=True)
                ]
                space = _past_busy(lambda: dataset.upsert_record_embeddings(model, answered, rows))
            done += len(batch_ids)
            sink.emit(ProgressEvent(phase="embed", done=done, total=total, unit="records"))

        if space is not None:
            sink.emit(ProgressEvent(phase="finalize", done=total, total=total, message="Building index"))
            indexed = space["id"]
            _past_busy(lambda: dataset.build_record_embedding_index(indexed))

        # Drop the API's cached Dataset so the newly written embeddings sidecar is picked up —
        # before marking the job done, so a client that polls "done" then queries sees embeddings.
        Dataset.invalidate_caches(dataset.info.id)
        store.update_job(
            job_id,
            status="done",
            progress=ProgressEvent(phase="embed", done=total, total=total, final=True).model_dump(),
        )
    except Exception as exc:  # noqa: BLE001 - surface as job error
        logger.exception("Embedding job %s failed", job_id)
        store.update_job(
            job_id,
            status="error",
            error={"type": type(exc).__name__, "message": str(exc), "trace": traceback.format_exc()},
        )
    finally:
        # Failed or cancelled too: a space emptied in place changed nothing the cache's stamp sees.
        Dataset.invalidate_caches(dataset.info.id)
        sink.close()
        client.close()


def submit_embedding_job(
    store: JobStore,
    dataset_path: Path,
    dataset_id: str,
    provider: InferenceProvider,
    model: str,
    batch_size: int = _EMBED_BATCH,
    force: bool = False,
) -> str:
    """Create an embedding job and start it in a background daemon thread.

    The connected provider supplies the server URL/key; the job then talks to it through a fresh
    synchronous client on its own thread. ``force`` empties the model's space first — to compute
    it again from nothing, or to repair it —, or deletes every model's embeddings when the dataset's
    `embeddings.json` cannot be read entirely.

    Returns:
        The job id (poll via ``GET /io/jobs/{id}``).
    """
    url = getattr(provider, "url", None)
    if not url:
        raise ValueError("The connected provider does not expose a server URL for embedding.")
    api_key = getattr(provider, "_api_key", None)
    job = store.create_job(kind="embed", dataset=dataset_id, spec={"model": model, "force": force})
    thread = threading.Thread(
        target=_run_embedding_job,
        args=(store, job.id, dataset_path, url, api_key, model, batch_size, force),
        daemon=True,
    )
    thread.start()
    return job.id
