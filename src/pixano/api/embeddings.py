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

import logging
import os
import threading
import traceback
from pathlib import Path
from typing import Any

from pixano_inference_client import EmbeddingRequest, SyncPixanoInferenceClient

from pixano.datasets.dataset import Dataset
from pixano.datasets.io.jobs import JobSink, JobStore
from pixano.datasets.io.progress import ProgressEvent
from pixano.inference.media import bytes_to_data_uri
from pixano.inference.provider import InferenceProvider


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


def _embed_images(client: SyncPixanoInferenceClient, model: str, images: list[str]) -> list[list[float]]:
    """Embed a batch of images via the SYNCHRONOUS client.

    The compute job runs in its own thread, so it must NOT reuse the connected provider's async
    httpx client (bound to the server's event loop); a fresh sync client avoids the cross-loop hang.
    """
    response = client.embedding(EmbeddingRequest(model=model, image=images))
    return response.data.embeddings.to_numpy().tolist()


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
        if force:
            # Repair/model-switch path: drop the table + sidecar so the space is rebuilt from
            # scratch (also escapes states where the sidecar points at a broken table).
            dataset.drop_record_embeddings()
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
                vectors = _embed_images(client, model, refs)
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
    synchronous client on its own thread. ``force`` drops the existing embedding table + sidecar
    first (repair / model switch).

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
