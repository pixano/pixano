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
import json
import shutil
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.locking import dataset_mutation_lock
from pixano.features import Image, Record
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import EmbeddingInput, EmbeddingOutput, EmbeddingResult, ModelInfo, NDArrayData


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

    def test_find_similar_searches_with_every_medium_of_the_record(self):
        """A record with two cameras is similar through either.

        r05 gets a second medium whose vector is r10's, orthogonal to its first: r10 must come
        right after r05 itself. The route used to read one vector of the record, whichever the
        table returned first.
        """
        dataset = _build_dataset(with_embeddings=True)
        dataset.add_data(
            "images",
            [Image.from_bytes(record_id="r05", logical_name="image", raw_bytes=_png_bytes(99), id="img05-back")],
            raise_or_warn="none",
        )
        dataset.add_record_embeddings([{"record_id": "r05", "view_id": "img05-back", "vector": _bit_vector(10)}])
        client = _make_client(dataset, _make_provider())

        body = client.post(f"{BASE}/records/search", json={"similar_to": "r05", "k": 2}).json()

        assert [item["id"] for item in body["items"]] == ["r05", "r10"]

    def test_find_similar_reads_a_record_id_holding_a_quote(self):
        """The record id went into the filter unescaped: a quote in it answered 503."""
        dataset = _build_dataset(with_embeddings=True)
        record_id = "o'brien"
        dataset.add_records(
            {
                "records": [Record(id=record_id)],
                "images": [
                    Image.from_bytes(
                        record_id=record_id, logical_name="image", raw_bytes=_png_bytes(99), id="img-o-brien"
                    )
                ],
            }
        )
        # Every bit set: no other record's vector, so the record is its own only nearest.
        dataset.add_record_embeddings([{"record_id": record_id, "vector": [1.0] * DIM}])
        client = _make_client(dataset, _make_provider())

        resp = client.post(f"{BASE}/records/search", json={"similar_to": record_id, "k": 1})

        assert resp.status_code == 200, resp.text
        assert [item["id"] for item in resp.json()["items"]] == [record_id]

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


def _fake_sync_client_factory(model: str = "mock-clip", served: str | None = None):
    """A stand-in for SyncPixanoInferenceClient: embeds each image batch to zero vectors.

    It lists the model with the checkpoint `served`, none when None.
    """

    def make(url, api_key=None):  # noqa: ANN001, ARG001
        instance = MagicMock()
        instance.list_models.return_value = [SimpleNamespace(name=model, model_path=served)]

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


# How long a computation of twelve images may take, and how often its job is asked about.
JOB_DEADLINE_S = 15
JOB_POLL_S = 0.1


def _computed(client: TestClient, model: str, force: bool = False, served: str | None = None) -> dict:
    """Run the application's own computation of a model's embeddings to its end; the job.

    Args:
        client: The application.
        model: The model to compute.
        force: Whether to compute it again from nothing.
        served: The checkpoint the inference tells it serves the model with; none told when None.
    """
    with patch(
        "pixano.api.embeddings.SyncPixanoInferenceClient", side_effect=_fake_sync_client_factory(model, served)
    ):
        resp = client.post(f"{BASE}/embeddings/compute", json={"model": model, "force": force})
        assert resp.status_code == 202, resp.text
        job_id = resp.json()["job_id"]
        deadline = time.time() + JOB_DEADLINE_S
        job = client.get(f"/io/jobs/{job_id}").json()
        while job["status"] not in {"done", "error", "cancelled"} and time.time() < deadline:
            time.sleep(JOB_POLL_S)
            job = client.get(f"/io/jobs/{job_id}").json()
    return job


class TestEmbeddingCorruption:
    """A broken embedding store must degrade to actionable errors + a repair path, never 500."""

    def _corrupt_missing_table(self, dataset: Dataset) -> Dataset:
        shutil.rmtree(dataset.path / "db" / f"{dataset.record_embedding_space()['table']}.lance")
        return dataset

    def _corrupt_dim(self, dataset: Dataset) -> Dataset:
        sidecar = dataset.path / "embeddings.json"
        document = json.loads(sidecar.read_text())
        document["spaces"][0]["dim"] = 16  # stored vectors are DIM=8
        sidecar.write_text(json.dumps(document))
        return dataset

    def test_filters_report_missing_table_and_stop_advertising_semantic(self):
        dataset = self._corrupt_missing_table(_build_dataset(with_embeddings=True))
        client = _make_client(dataset)
        search = client.get(f"{BASE}/filters").json()["search"]
        assert search["modes"] == ["text"]
        assert search["status"] == "missing_table"
        assert search["detail"]

    def test_filters_report_dim_mismatch(self):
        dataset = self._corrupt_dim(_build_dataset(with_embeddings=True))
        client = _make_client(dataset)
        search = client.get(f"{BASE}/filters").json()["search"]
        assert search["modes"] == ["text"]
        assert search["status"] == "dim_mismatch"

    def test_search_on_missing_table_is_503_not_500(self):
        dataset = self._corrupt_missing_table(_build_dataset(with_embeddings=True))
        client = _make_client(dataset, _make_provider())
        resp = client.post(f"{BASE}/records/search", json={"text": "record 1"})
        assert resp.status_code == 503
        assert "ecompute" in resp.json()["detail"]  # actionable: "Recompute the embeddings"

    def test_search_on_dim_mismatch_is_409(self):
        dataset = self._corrupt_dim(_build_dataset(with_embeddings=True))
        client = _make_client(dataset, _make_provider())
        resp = client.post(f"{BASE}/records/search", json={"text": "record 1"})
        assert resp.status_code == 409

    def test_recompute_without_force_is_409_when_broken(self):
        dataset = self._corrupt_missing_table(_build_dataset(with_embeddings=True))
        client = _make_client(dataset, _make_provider())
        resp = client.post(f"{BASE}/embeddings/compute", json={"model": "mock-clip"})
        assert resp.status_code == 409
        assert "force" in resp.json()["detail"]

    def test_another_model_is_computed_beside_without_force(self):
        """Its vectors go to a space of their own: the first model's are left as they are."""
        dataset = _build_dataset(with_embeddings=True)
        client = _make_client(dataset, _make_provider())

        job = _computed(client, "another-model")

        assert job["status"] == "done", job
        spaces = {space["model_id"]: space for space in client.get(f"{BASE}/embedding-spaces").json()}
        assert set(spaces) == {"mock-clip", "another-model"}
        assert (spaces["mock-clip"]["default"], spaces["mock-clip"]["embedded_rows"]) == (True, 0)
        reopened = Dataset(dataset.path)
        assert reopened.open_table(reopened.record_embedding_space("mock-clip")["table"]).count_rows() == 12

    def test_force_recompute_repairs_a_broken_store(self):
        dataset = self._corrupt_missing_table(_build_dataset(with_embeddings=True))
        client = _make_client(dataset, _make_provider())

        job = _computed(client, "mock-clip", force=True)

        assert job["status"] == "done", job
        search = client.get(f"{BASE}/filters").json()["search"]
        assert search["status"] == "ready"
        assert "semantic" in search["modes"]

    def test_force_recompute_repairs_a_dimension_the_description_got_wrong(self):
        """The space keeps its id and the default; its table is made again at the vectors' dimension."""
        dataset = self._corrupt_dim(_build_dataset(with_embeddings=True))
        held = Dataset(dataset.path).record_embedding_space()
        client = _make_client(dataset, _make_provider())

        job = _computed(client, "mock-clip", force=True)

        assert job["status"] == "done", job
        (space,) = client.get(f"{BASE}/embedding-spaces").json()
        assert (space["id"], space["dim"], space["default"], space["status"]) == (held["id"], DIM, True, "ready")

    def test_a_description_that_cannot_be_read_entirely_is_computed_again_with_force_only(self):
        dataset = _build_dataset(with_embeddings=True)
        (dataset.path / "embeddings.json").write_text("{")
        client = _make_client(dataset, _make_provider())

        refused = client.post(f"{BASE}/embeddings/compute", json={"model": "mock-clip"})
        search = client.get(f"{BASE}/filters").json()["search"]
        job = _computed(client, "mock-clip", force=True)

        assert refused.status_code == 409 and "deletes every model's embeddings" in refused.json()["detail"]
        assert (search["fully_read"], search["status"]) == (False, "corrupt")
        assert job["status"] == "done", job
        assert [space["model_id"] for space in client.get(f"{BASE}/embedding-spaces").json()] == ["mock-clip"]


class TestComputeJob:
    def test_compute_embeddings_end_to_end(self):
        client = _make_client(_build_dataset(with_embeddings=False), _make_provider())

        job = _computed(client, "mock-clip")

        assert job["status"] == "done", job
        # The dataset now advertises semantic search.
        search = client.get(f"{BASE}/filters").json()["search"]
        assert "semantic" in search["modes"]

    def test_the_checkpoint_the_inference_tells_names_the_space(self):
        client = _make_client(_build_dataset(with_embeddings=False), _make_provider())

        job = _computed(client, "mock-clip", served="mock-v1")

        assert job["status"] == "done", job
        (space,) = client.get(f"{BASE}/embedding-spaces").json()
        assert space["checkpoint"] == "mock-v1"

    def test_an_inference_that_cannot_say_which_weights_it_serves_fails_the_computation(self):
        """By name only, it could write into another checkpoint's space."""
        client = _make_client(_build_dataset(with_embeddings=False), _make_provider())
        unreachable = MagicMock()
        unreachable.list_models.side_effect = ConnectionError("the inference is restarting")

        with patch("pixano.api.embeddings.SyncPixanoInferenceClient", return_value=unreachable):
            job_id = client.post(f"{BASE}/embeddings/compute", json={"model": "mock-clip"}).json()["job_id"]
            deadline = time.time() + JOB_DEADLINE_S
            job = client.get(f"/io/jobs/{job_id}").json()
            while job["status"] not in {"done", "error", "cancelled"} and time.time() < deadline:
                time.sleep(JOB_POLL_S)
                job = client.get(f"/io/jobs/{job_id}").json()

        assert job["status"] == "error"
        assert "restarting" in job["error"]["message"]


# The second model's vectors: each record where the first model puts its mirror, 11 - i.
SIGLIP = "mock-siglip"


def _with_a_second_model(dataset: Dataset) -> dict:
    space = dataset.ensure_record_embedding_space(SIGLIP, "so400m", dim=DIM)
    dataset.add_record_embeddings(
        [{"record_id": f"r{i:02d}", "view_id": f"img{i:02d}", "vector": _bit_vector(11 - i)} for i in range(12)],
        space["id"],
    )
    return space


class TestSeveralModels:
    """A dataset of two models: a search names the one it reads, the default otherwise."""

    def test_filters_list_every_model_with_its_health_the_default_first(self):
        dataset = _build_dataset(with_embeddings=True)
        _with_a_second_model(dataset)
        client = _make_client(dataset)

        search = client.get(f"{BASE}/filters").json()["search"]

        assert search["models"] == ["mock-clip", SIGLIP]
        assert [(space["model_id"], space["default"], space["status"]) for space in search["spaces"]] == [
            ("mock-clip", True, "partial"),
            (SIGLIP, False, "ready"),
        ]

    def test_a_text_search_reads_the_model_it_names(self):
        dataset = _build_dataset(with_embeddings=True)
        siglip = _with_a_second_model(dataset)
        client = _make_client(dataset, _make_provider())

        by_default = client.post(f"{BASE}/records/search", json={"text": "record 5", "k": 1}).json()
        by_name = client.post(f"{BASE}/records/search", json={"text": "record 5", "k": 1, "model": SIGLIP}).json()
        by_id = client.post(f"{BASE}/records/search", json={"text": "record 5", "k": 1, "model": siglip["id"]}).json()

        assert (by_default["items"][0]["id"], by_default["model"]) == ("r05", "mock-clip")
        # r06 is the record the second model puts at 5 (11 - 6).
        assert (by_name["items"][0]["id"], by_name["model"], by_name["space"]) == ("r06", SIGLIP, siglip["id"])
        assert by_id["items"][0]["id"] == "r06"

    def test_a_similar_search_reads_the_records_vectors_of_the_model_it_names(self):
        """The record itself first in either; next, r04 for the first model (5 xor 1), r07 for the second."""
        dataset = _build_dataset(with_embeddings=True)
        _with_a_second_model(dataset)
        client = _make_client(dataset, _make_provider())

        by_default = client.post(f"{BASE}/records/search", json={"similar_to": "r05", "k": 2}).json()
        by_name = client.post(f"{BASE}/records/search", json={"similar_to": "r05", "k": 2, "model": SIGLIP}).json()

        assert [item["id"] for item in by_default["items"]][0] == "r05"
        assert [item["id"] for item in by_name["items"]][0] == "r05"
        assert by_default["items"][1]["id"] != by_name["items"][1]["id"]
        assert by_name["model"] == SIGLIP

    def test_a_model_the_dataset_holds_no_embeddings_of_is_400(self):
        client = _make_client(_build_dataset(with_embeddings=True), _make_provider())

        resp = client.post(f"{BASE}/records/search", json={"text": "record 5", "model": "dinov2"})

        assert resp.status_code == 400
        assert "dinov2" in resp.json()["detail"]

    def test_another_model_made_the_default_is_the_one_a_search_reads(self):
        dataset = _build_dataset(with_embeddings=True)
        siglip = _with_a_second_model(dataset)
        client = _make_client(dataset, _make_provider())

        resp = client.put(f"{BASE}/embedding-spaces/default", json={"space_id": siglip["id"]})
        body = client.post(f"{BASE}/records/search", json={"text": "record 5", "k": 1}).json()

        assert (resp.status_code, resp.json()["default"]) == (200, True)
        assert body["items"][0]["id"] == "r06"

    def test_a_space_the_dataset_does_not_hold_is_404(self):
        client = _make_client(_build_dataset(with_embeddings=True))

        assert client.put(f"{BASE}/embedding-spaces/default", json={"space_id": "dinov2-00000000"}).status_code == 404
        assert client.delete(f"{BASE}/embedding-spaces/dinov2-00000000").status_code == 404
        # A model's name is no space's id: two checkpoints may share it.
        assert client.delete(f"{BASE}/embedding-spaces/mock-clip").status_code == 404

    def test_deleting_a_models_embeddings_leaves_the_others(self):
        dataset = _build_dataset(with_embeddings=True)
        siglip = _with_a_second_model(dataset)
        client = _make_client(dataset, _make_provider())

        resp = client.delete(f"{BASE}/embedding-spaces/{siglip['id']}")

        assert resp.status_code == 204
        assert [space["model_id"] for space in client.get(f"{BASE}/embedding-spaces").json()] == ["mock-clip"]
        body = client.post(f"{BASE}/records/search", json={"text": "record 5", "k": 1}).json()
        assert body["items"][0]["id"] == "r05"

    def test_recomputing_a_model_with_force_empties_that_model_only(self):
        dataset = _build_dataset(with_embeddings=True)
        siglip = _with_a_second_model(dataset)
        held = Dataset(dataset.path).record_embedding_space("mock-clip")
        client = _make_client(dataset, _make_provider())

        job = _computed(client, "mock-clip", force=True)

        assert job["status"] == "done", job
        reopened = Dataset(dataset.path)
        clip = reopened.record_embedding_space("mock-clip")
        assert (clip["id"], reopened.record_embedding_space()["id"]) == (held["id"], held["id"])
        assert reopened.record_embedding_health(clip["id"])["status"] == "ready"
        assert reopened.open_table(siglip["table"]).count_rows() == 12

    def test_a_broken_default_offers_no_search_naming_no_model_but_the_model_that_is_fine(self):
        dataset = _build_dataset(with_embeddings=True)
        _with_a_second_model(dataset)
        shutil.rmtree(dataset.path / "db" / f"{dataset.record_embedding_space()['table']}.lance")
        client = _make_client(dataset, _make_provider())

        search = client.get(f"{BASE}/filters").json()["search"]
        without_model = client.post(f"{BASE}/records/search", json={"text": "record 5"})
        with_model = client.post(f"{BASE}/records/search", json={"text": "record 5", "model": SIGLIP})

        assert (search["modes"], search["models"], search["status"]) == (["text"], [SIGLIP], "missing_table")
        assert (without_model.status_code, with_model.status_code) == (503, 200)

    def test_deleting_the_default_hands_it_to_the_model_left(self):
        dataset = _build_dataset(with_embeddings=True)
        _with_a_second_model(dataset)
        default = Dataset(dataset.path).record_embedding_space()
        client = _make_client(dataset, _make_provider())

        client.delete(f"{BASE}/embedding-spaces/{default['id']}")

        (space,) = client.get(f"{BASE}/embedding-spaces").json()
        assert (space["model_id"], space["default"]) == (SIGLIP, True)
        assert f"{default['table']}.lance" not in {path.name for path in (dataset.path / "db").iterdir()}

    def test_no_space_is_an_empty_list(self):
        client = _make_client(_build_dataset(with_embeddings=False))

        assert client.get(f"{BASE}/embedding-spaces").json() == []

    def test_a_dataset_someone_else_writes_answers_busy(self):
        dataset = _build_dataset(with_embeddings=True)
        siglip = _with_a_second_model(dataset)
        client = _make_client(dataset)

        with dataset_mutation_lock(dataset.path):
            resp = client.put(f"{BASE}/embedding-spaces/default", json={"space_id": siglip["id"]})

        assert (resp.status_code, resp.json()["detail"]["code"]) == (409, "dataset_busy")

    def test_a_description_that_cannot_be_read_entirely_changes_through_force_only(self):
        dataset = _build_dataset(with_embeddings=True)
        siglip = _with_a_second_model(dataset)
        sidecar = dataset.path / "embeddings.json"
        document = json.loads(sidecar.read_text())
        document["version"] = 99
        sidecar.write_text(json.dumps(document))
        client = _make_client(dataset)

        resp = client.put(f"{BASE}/embedding-spaces/default", json={"space_id": siglip["id"]})

        assert resp.status_code == 409
        assert "force=true" in resp.json()["detail"]

    def test_a_text_search_is_refused_when_the_inference_serves_other_weights(self):
        """Embedded by other weights than the stored vectors, the query would rank them by nothing."""
        dataset = _build_dataset(with_embeddings=False)
        space = dataset.ensure_record_embedding_space("mock-clip", "mock-v1", dim=DIM)
        dataset.add_record_embeddings(
            [{"record_id": "r01", "view_id": "img01", "vector": _bit_vector(1)}], space["id"]
        )
        provider = _make_provider()
        provider.list_models = AsyncMock(
            return_value=[ModelInfo(name="mock-clip", task="embedding", model_path="mock-v2")]
        )
        client = _make_client(dataset, provider)

        resp = client.post(f"{BASE}/records/search", json={"text": "record 1"})

        assert resp.status_code == 409
        assert "mock-v2" in resp.json()["detail"]
