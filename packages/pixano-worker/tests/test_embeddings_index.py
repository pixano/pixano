# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""An embeddings job, through the queue, ends by indexing the vectors it wrote.

Everything runs as in production but the inference server, which stands in at its HTTP edge:
the job is planned and run by the runner against a live PostgreSQL, the chunks write a real
dataset whose images sit on disk, the final chunk indexes the table, and the application's
search reads it.
"""

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import psycopg
import pytest
from PIL import Image as PILImage
from pixano_inference.client import SyncPixanoInferenceClient
from pixano_inference.schemas import NDArrayFloat
from pixano_worker import runner
from pixano_worker import writer as writer_module
from pixano_worker.kinds import EmbeddingsKind, Registry
from pixano_worker.media import MediaResolver
from pixano_worker.schema import SCHEMA_NAME
from psycopg.types.json import Jsonb

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import Image, Record


DATASET_ID = "photos"
# Enough images to train a vector index once the threshold is brought down to them.
IMAGES = 300
DIM = 16
# The same media storage, mounted elsewhere by the inference: the worker sends it this path.
INFERENCE_MEDIA_ROOT = "/inference-media"


def _vector_of(path: str) -> list[float]:
    """The vector the stand-in model gives an image: its own, the same at every call."""
    rank = int(Path(path).stem.removeprefix("img-"))
    return np.random.default_rng(rank).standard_normal(DIM).tolist()


class _Inference:
    """An embedding model at its HTTP edge, answering as the real server does."""

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "clip",
                        "capability": "embedding",
                        "modelClass": "OpenClipEmbeddingModel",
                        "modelPath": "MobileCLIP2-S2",
                        "status": "RUNNING",
                    }
                ],
            )
        body = json.loads(request.content)
        if request.url.path != "/v1/inference/embedding":
            return httpx.Response(404, json={"detail": "Not Found"})
        vectors = np.array([_vector_of(image) for image in body["image"]], dtype=np.float32)
        return httpx.Response(
            200,
            json={
                "id": "ray-clip-0",
                "status": "SUCCESS",
                "timestamp": "2026-11-02T00:00:00Z",
                "processingTime": 0.1,
                "metadata": {"model_class": "OpenClipEmbeddingModel", "model_path": "MobileCLIP2-S2"},
                "data": {"embeddings": NDArrayFloat.from_numpy(vectors).model_dump(), "dim": DIM},
            },
        )


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, MediaResolver]:
    """A library holding one dataset of images on disk, and how the worker designates them."""
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    media_root = tmp_path / "media"
    media_root.mkdir()
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID, DatasetInfo(id=DATASET_ID, name="Photos", record=Record, views={"image": Image})
    )
    dataset.add_records({"records": [Record(id=f"rec-{n}") for n in range(IMAGES)]})
    images = []
    for n in range(IMAGES):
        PILImage.new("RGB", (4, 4)).save(media_root / f"img-{n}.png")
        images.append(
            Image(
                id=f"img-{n}",
                record_id=f"rec-{n}",
                logical_name="image",
                uri=str(media_root / f"img-{n}.png"),
                width=4,
                height=4,
            )
        )
    dataset.add_data("images", images, raise_or_warn="none")

    transport = httpx.MockTransport(_Inference().handle)
    monkeypatch.setattr(
        "pixano_worker.kinds.inference.SyncPixanoInferenceClient",
        lambda url, **kwargs: SyncPixanoInferenceClient(url, transport=transport, **kwargs),
    )
    return library, MediaResolver(str(media_root), INFERENCE_MEDIA_ROOT)


@pytest.fixture
def registry(db: psycopg.Connection) -> Registry:
    registry = Registry()
    registry.register(EmbeddingsKind("http://inference", ""))
    registry.declare(db, "worker-test")
    return registry


async def _embed(
    db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, library: tuple[Path, MediaResolver]
) -> str:
    """Submit an embeddings job, plan it and run it to its end; return its identifier."""
    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params) VALUES ('embeddings', %s, %s) RETURNING id",
        (DATASET_ID, Jsonb({"model": "clip", "chunk_size": 32})),
    ).fetchone()
    assert row is not None
    path, media = library
    await runner.plan_one(adb, registry, library=path, media=media)
    while await runner.run_batch(adb, registry, "worker-test", 8, library=path, media=media):
        pass
    return str(row[0])


def _indexes(dataset: Dataset) -> dict[str, str]:
    """The embeddings table's indexes, by the column each covers."""
    return {index.columns[0]: index.index_type for index in dataset.open_table("embeddings").list_indices()}


def _outcome(db: psycopg.Connection, job: str) -> tuple[Any, ...]:
    row = db.execute(
        f"SELECT j.state, f.state FROM {SCHEMA_NAME}.jobs j "
        f"JOIN {SCHEMA_NAME}.job_chunks f ON f.job_id = j.id AND f.final WHERE j.id = %s",
        (job,),
    ).fetchone()
    assert row is not None
    return row


class TestTheJobIndexesItsVectors:
    async def test_a_large_table_ends_with_a_vector_index_the_search_reads(
        self,
        db: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        library: tuple[Path, MediaResolver],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(writer_module, "VECTOR_INDEX_MIN_ROWS", IMAGES)

        job = await _embed(db, adb, registry, library)

        assert _outcome(db, job) == ("done", "done")
        dataset = Dataset(library[0] / DATASET_ID)
        assert _indexes(dataset) == {"record_id": "BTree", "vector": "IvfSq"}
        records, _ = dataset.search_records(_vector_of("img-42.png"), k=1)
        assert [record.id for record in records] == ["rec-42"]

    async def test_a_small_table_ends_with_its_record_index_only(
        self,
        db: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        library: tuple[Path, MediaResolver],
    ) -> None:
        """Under the threshold, exact search stays: an index would only lose results."""
        job = await _embed(db, adb, registry, library)

        assert _outcome(db, job) == ("done", "done")
        assert _indexes(Dataset(library[0] / DATASET_ID)) == {"record_id": "BTree"}

    async def test_an_index_that_fails_to_build_is_tried_again_later(
        self,
        db: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        library: tuple[Path, MediaResolver],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Another writer's commit conflicting with the index's fails the build, not the job.

        Every vector is written: the final chunk is handed back, and the next attempt builds the index.
        """
        monkeypatch.setattr(writer_module, "VECTOR_INDEX_MIN_ROWS", IMAGES)
        index_embeddings = writer_module.JobWriter.index_embeddings
        conflicts = [RuntimeError("Commit conflict for version 12: another writer committed meanwhile")]

        def conflicting_once(self: Any, min_rows: int | None = None) -> str | None:
            if conflicts:
                raise conflicts.pop()
            return index_embeddings(self, min_rows)

        monkeypatch.setattr(writer_module.JobWriter, "index_embeddings", conflicting_once)

        job = await _embed(db, adb, registry, library)

        final = db.execute(
            f"SELECT state, error->>'reason', error->>'detail' FROM {SCHEMA_NAME}.job_chunks "
            "WHERE job_id = %s AND final",
            (job,),
        ).fetchone()
        assert final is not None and final[:2] == ("pending", "transient failure")
        assert "could not be indexed" in final[2]

        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now() WHERE job_id = %s AND final", (job,))
        path, media = library
        while await runner.run_batch(adb, registry, "worker-test", 8, library=path, media=media):
            pass

        assert _outcome(db, job) == ("done", "done")
        assert _indexes(Dataset(path / DATASET_ID)) == {"record_id": "BTree", "vector": "IvfSq"}
