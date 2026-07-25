# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Record-embedding computation job.

Computes one CLIP-style vector per record from its image view by calling the connected
pixano-inference provider, writes the vectors to the dataset's record-embedding table, and builds
the vector index. Runs in a background thread tracked in the shared `JobStore`, so progress is
polled through the existing ``/io/jobs/{id}`` endpoint. Idempotent: records already embedded are
skipped (resume-safe).
"""

import asyncio
import logging
import os
import threading
import traceback
from pathlib import Path
from typing import Any

from pixano.datasets.dataset import Dataset
from pixano.datasets.io.jobs import JobSink, JobStore
from pixano.datasets.io.progress import ProgressEvent
from pixano.inference.media import bytes_to_data_uri
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import EmbeddingInput, EmbeddingResult


logger = logging.getLogger(__name__)

_IMAGE_TABLE = "images"
_EMBED_BATCH = 16


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


def _embed_images(provider: InferenceProvider, model: str, images: list[str]) -> list[list[float]]:
    """Call the provider's (async) embedding task for a batch of images, on this thread."""

    async def _call() -> EmbeddingResult:
        return await provider.embedding(EmbeddingInput(model=model, image=images))

    result = asyncio.run(_call())
    dim = result.data.dim
    values = result.data.embedding.values
    return [values[i * dim : (i + 1) * dim] for i in range(len(images))]


def _run_embedding_job(
    store: JobStore,
    job_id: str,
    dataset_path: Path,
    provider: InferenceProvider,
    model: str,
    batch_size: int,
) -> None:
    dataset = Dataset(dataset_path)
    store.update_job(job_id, status="running", pid=os.getpid(), heartbeat=True)
    sink = JobSink(store, job_id)
    try:
        record_ids: list[str] = dataset.get_all_ids("records")
        already: set[str] = set()
        if dataset.has_record_embeddings():
            existing = dataset.get_data(dataset._RECORD_EMBEDDING_TABLE, limit=None)  # noqa: SLF001
            already = {row.record_id for row in (existing or [])}
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
                vectors = _embed_images(provider, model, refs)
                if not dataset.has_record_embeddings():
                    dataset.create_record_embedding_table(dim=len(vectors[0]), model_id=model)
                dataset.add_record_embeddings(
                    [
                        {"record_id": rid, "view_id": by_record[rid].id, "vector": vector}
                        for rid, vector in zip(ordered_ids, vectors, strict=True)
                    ]
                )
            done += len(batch_ids)
            sink.emit(ProgressEvent(phase="embed", done=done, total=total, unit="records"))

        if dataset.has_record_embeddings():
            sink.emit(ProgressEvent(phase="finalize", done=total, total=total, message="Building index"))
            dataset.build_record_embedding_index()

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
        sink.close()


def submit_embedding_job(
    store: JobStore,
    dataset_path: Path,
    dataset_id: str,
    provider: InferenceProvider,
    model: str,
    batch_size: int = _EMBED_BATCH,
) -> str:
    """Create an embedding job and start it in a background daemon thread.

    Returns:
        The job id (poll via ``GET /io/jobs/{id}``).
    """
    job = store.create_job(kind="embed", dataset=dataset_id, spec={"model": model})
    thread = threading.Thread(
        target=_run_embedding_job,
        args=(store, job.id, dataset_path, provider, model, batch_size),
        daemon=True,
    )
    thread.start()
    return job.id
