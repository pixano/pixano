# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""End-to-end tests for semantic search: /filters capability, /records/search, compute job.

The inference provider is a mock returning deterministic vectors, so no server or model is
required. Record embeddings are seeded directly (bring-your-own vectors).
"""

import io
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.features import Image, Record
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import EmbeddingInput, EmbeddingOutput, EmbeddingResult, NDArrayData


DATASET_ID = "semantic_dataset"
DIM = 8


def _bit_vector(i: int) -> list[float]:
    return [float((i >> b) & 1) for b in range(DIM)]


def _png_bytes(seed: int) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (8, 8), color=(seed * 10 % 256, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _make_provider() -> MagicMock:
    provider = MagicMock(spec=InferenceProvider)
    provider.name = "mock-embed"
    provider.url = "http://mock"

    async def embedding(input_data: EmbeddingInput, timeout: float = 60.0) -> EmbeddingResult:
        # Text "record N" embeds to record N's vector; image batches embed to zeros.
        if input_data.text is not None:
            texts = input_data.text if isinstance(input_data.text, list) else [input_data.text]
            vectors = [_bit_vector(int(t.split()[-1])) for t in texts]
        else:
            images = input_data.image if isinstance(input_data.image, list) else [input_data.image]
            vectors = [[0.0] * DIM for _ in images]
        flat = [v for vec in vectors for v in vec]
        from datetime import datetime

        return EmbeddingResult(
            data=EmbeddingOutput(embedding=NDArrayData(values=flat, shape=[len(vectors), DIM]), dim=DIM),
            timestamp=datetime.now(),
            processing_time=0.01,
            metadata={},
        )

    provider.embedding = AsyncMock(side_effect=embedding)
    return provider


def _make_client(dataset: Dataset, provider: MagicMock | None = None) -> TestClient:
    tmp = Path(tempfile.mkdtemp())
    models_dir = tmp / "models"
    models_dir.mkdir()
    kwargs: dict = {"library_dir": str(dataset.path.parent), "models_dir": str(models_dir)}
    if provider is not None:
        kwargs["inference_providers"] = {"mock-embed": provider}
        kwargs["default_inference_provider"] = "mock-embed"
    settings = Settings(**kwargs)

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app)


def _build_dataset(with_embeddings: bool) -> Dataset:
    target = Path(tempfile.mkdtemp()) / "library" / DATASET_ID
    dataset = Dataset.create(
        target,
        DatasetInfo(id=DATASET_ID, name=DATASET_ID, description="d", record=Record, views={"image": Image}),
    )
    records = [Record(id=f"r{i:02d}") for i in range(12)]
    images = [
        Image.from_bytes(record_id=f"r{i:02d}", logical_name="image", raw_bytes=_png_bytes(i), id=f"img{i:02d}")
        for i in range(12)
    ]
    dataset.add_records({"records": records, "images": images})
    if with_embeddings:
        dataset.create_record_embedding_table(dim=DIM, model_id="mock-clip")
        dataset.add_record_embeddings([{"record_id": f"r{i:02d}", "vector": _bit_vector(i)} for i in range(12)])
        dataset.build_record_embedding_index()
    return dataset


BASE = f"/datasets/{DATASET_ID}"


class TestSearchCapability:
    def test_filters_advertise_no_semantic_without_embeddings(self):
        client = _make_client(_build_dataset(with_embeddings=False))
        search = client.get(f"{BASE}/filters").json()["search"]
        assert search["modes"] == ["text"]
        assert search["models"] == []

    def test_filters_advertise_semantic_with_embeddings(self):
        client = _make_client(_build_dataset(with_embeddings=True))
        search = client.get(f"{BASE}/filters").json()["search"]
        assert "semantic" in search["modes"]
        assert search["models"] == ["mock-clip"]


class TestRecordSearch:
    def test_text_search_ranks_records(self):
        provider = _make_provider()
        client = _make_client(_build_dataset(with_embeddings=True), provider)
        body = client.post(f"{BASE}/records/search", json={"text": "record 5", "k": 3}).json()
        assert body["mode"] == "text"
        assert body["items"][0]["id"] == "r05"
        assert body["items"][0]["_distance"] == pytest.approx(0.0, abs=1e-6)
        provider.embedding.assert_awaited()

    def test_find_similar_uses_stored_vector_without_the_provider(self):
        provider = _make_provider()
        client = _make_client(_build_dataset(with_embeddings=True), provider)
        body = client.post(f"{BASE}/records/search", json={"similar_to": "r07", "k": 2}).json()
        assert body["mode"] == "similar"
        assert body["items"][0]["id"] == "r07"
        provider.embedding.assert_not_awaited()  # stored vector → no query encoding

    def test_search_with_filter_prefilter(self):
        provider = _make_provider()
        client = _make_client(_build_dataset(with_embeddings=True), provider)
        body = client.post(
            f"{BASE}/records/search",
            json={"text": "record 5", "k": 5, "filter": ["id:in:r01,r03,r05"]},
        ).json()
        assert {item["id"] for item in body["items"]} <= {"r01", "r03", "r05"}
        assert body["items"][0]["id"] == "r05"

    def test_search_without_embeddings_is_400(self):
        client = _make_client(_build_dataset(with_embeddings=False), _make_provider())
        resp = client.post(f"{BASE}/records/search", json={"text": "record 1"})
        assert resp.status_code == 400

    def test_search_requires_text_or_similar_to(self):
        client = _make_client(_build_dataset(with_embeddings=True), _make_provider())
        resp = client.post(f"{BASE}/records/search", json={"k": 3})
        assert resp.status_code == 400


def _fake_sync_client_factory():
    """A stand-in for SyncPixanoInferenceClient: embeds each image batch to zero vectors."""

    def make(url, api_key=None):  # noqa: ANN001, ARG001
        instance = MagicMock()

        def embedding(request):  # noqa: ANN001
            images = request.image if isinstance(request.image, list) else [request.image]
            arr = np.zeros((len(images), DIM), dtype=np.float32)
            response = MagicMock()
            response.data.embeddings.to_numpy.return_value = arr
            response.data.dim = DIM
            return response

        instance.embedding.side_effect = embedding
        instance.close.return_value = None
        return instance

    return make


class TestComputeJob:
    def test_compute_embeddings_end_to_end(self):
        provider = _make_provider()
        client = _make_client(_build_dataset(with_embeddings=False), provider)
        # The background job uses a fresh SYNC client (not the async provider), so patch it.
        with patch(
            "pixano.api.embeddings.SyncPixanoInferenceClient",
            side_effect=_fake_sync_client_factory(),
        ):
            resp = client.post(f"{BASE}/embeddings/compute", json={"model": "mock-clip"})
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

            # Poll the shared job endpoint until the background thread finishes.
            deadline = time.time() + 15
            status = "pending"
            while time.time() < deadline:
                status = client.get(f"/io/jobs/{job_id}").json()["status"]
                if status in {"done", "error", "cancelled"}:
                    break
                time.sleep(0.1)
            assert status == "done", client.get(f"/io/jobs/{job_id}").json()

        # The dataset now advertises semantic search.
        search = client.get(f"{BASE}/filters").json()["search"]
        assert "semantic" in search["modes"]
