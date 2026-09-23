# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Record-level embedding storage + vector search (no ML model involved)."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.utils.errors import DatasetAccessError
from pixano.features import Image, Record


def _bit_vector(i: int, dim: int = 8) -> list[float]:
    return [float((i >> b) & 1) for b in range(dim)]


@pytest.fixture()
def dataset_with_embeddings() -> Dataset:
    tmp = Path(tempfile.mkdtemp()) / "ds"
    dataset = Dataset.create(tmp, DatasetInfo(name="emb", description="d", record=Record, views={"image": Image}))
    dataset.add_records({"records": [Record(id=f"r{i}") for i in range(20)]})
    dataset.create_record_embedding_table(dim=8, model_id="test-clip", metric="cosine")
    dataset.add_record_embeddings([{"record_id": f"r{i}", "vector": _bit_vector(i)} for i in range(20)])
    dataset.build_record_embedding_index()
    return dataset


class TestRecordEmbeddingStorage:
    def test_space_is_recorded(self, dataset_with_embeddings: Dataset):
        assert dataset_with_embeddings.has_record_embeddings()
        space = dataset_with_embeddings.record_embedding_space()
        assert space["model_id"] == "test-clip"
        assert space["dim"] == 8
        assert space["metric"] == "cosine"

    def test_embedding_table_opens_without_a_model(self, dataset_with_embeddings: Dataset):
        # A plain Embedding table must open with no embedding-function registration.
        table = dataset_with_embeddings.open_table("embeddings")
        assert table.count_rows() == 20

    def test_search_ranks_by_distance(self, dataset_with_embeddings: Dataset):
        records, distances = dataset_with_embeddings.search_records(_bit_vector(5), k=3)
        assert records[0].id == "r5"
        assert distances[0] == pytest.approx(0.0, abs=1e-6)
        assert distances == sorted(distances)

    def test_search_respects_record_id_prefilter(self, dataset_with_embeddings: Dataset):
        records, _ = dataset_with_embeddings.search_records(_bit_vector(5), k=5, record_id_filter=["r1", "r3", "r5"])
        assert {r.id for r in records} <= {"r1", "r3", "r5"}
        assert records[0].id == "r5"

    def test_empty_prefilter_returns_nothing(self, dataset_with_embeddings: Dataset):
        assert dataset_with_embeddings.search_records(_bit_vector(5), k=5, record_id_filter=[]) == ([], [])

    def test_sidecar_persists_across_reopen(self, dataset_with_embeddings: Dataset):
        reopened = Dataset(dataset_with_embeddings.path)
        assert reopened.has_record_embeddings()
        records, _ = reopened.search_records(_bit_vector(5), k=1)
        assert records[0].id == "r5"

    def test_search_without_embeddings_raises(self):
        tmp = Path(tempfile.mkdtemp()) / "empty"
        dataset = Dataset.create(
            tmp, DatasetInfo(name="empty", description="d", record=Record, views={"image": Image})
        )
        assert not dataset.has_record_embeddings()
        with pytest.raises(DatasetAccessError):
            dataset.search_records(_bit_vector(0), k=1)


def _embeddings_table_dir(dataset: Dataset) -> Path:
    return dataset.path / "db" / "embeddings.lance"


class TestRecordEmbeddingHealth:
    def test_ready(self, dataset_with_embeddings: Dataset):
        health = dataset_with_embeddings.record_embedding_health()
        assert health["status"] == "ready"
        assert health["model_id"] == "test-clip"
        assert health["rows"] == 20
        assert health["records"] == 20

    def test_absent_without_sidecar(self):
        tmp = Path(tempfile.mkdtemp()) / "none"
        dataset = Dataset.create(tmp, DatasetInfo(name="none", description="d", record=Record, views={"image": Image}))
        assert dataset.record_embedding_health()["status"] == "absent"

    def test_partial_when_some_records_missing(self, dataset_with_embeddings: Dataset):
        dataset_with_embeddings.add_records({"records": [Record(id="extra")]})
        health = dataset_with_embeddings.record_embedding_health()
        assert health["status"] == "partial"
        assert health["rows"] == 20
        assert health["records"] == 21

    def test_missing_table_detected(self, dataset_with_embeddings: Dataset):
        # Sidecar remains but the physical table is gone (crashed job / external delete).
        shutil.rmtree(_embeddings_table_dir(dataset_with_embeddings))
        reopened = Dataset(dataset_with_embeddings.path)
        assert reopened.has_record_embeddings()  # sidecar still advertises...
        assert reopened.record_embedding_health()["status"] == "missing_table"  # ...health does not

    def test_dim_mismatch_detected(self, dataset_with_embeddings: Dataset):
        sidecar = dataset_with_embeddings.path / "embeddings.json"
        space = json.loads(sidecar.read_text())
        space["dim"] = 16  # stored vectors are dim 8
        sidecar.write_text(json.dumps(space))
        reopened = Dataset(dataset_with_embeddings.path)
        assert reopened.record_embedding_health()["status"] == "dim_mismatch"

    def test_empty_table_detected(self):
        tmp = Path(tempfile.mkdtemp()) / "empty_table"
        dataset = Dataset.create(tmp, DatasetInfo(name="e", description="d", record=Record, views={"image": Image}))
        dataset.add_records({"records": [Record(id="r0")]})
        dataset.create_record_embedding_table(dim=8, model_id="m")
        assert dataset.record_embedding_health()["status"] == "empty"

    def test_corrupt_sidecar_degrades_instead_of_bricking_the_dataset(self, dataset_with_embeddings: Dataset):
        sidecar = dataset_with_embeddings.path / "embeddings.json"
        space = json.loads(sidecar.read_text())
        space["dim"] = 0  # previously raised out of Dataset.__init__ → 500 on EVERY endpoint
        sidecar.write_text(json.dumps(space))
        reopened = Dataset(dataset_with_embeddings.path)
        assert not reopened.has_record_embeddings()
        assert reopened.record_embedding_health()["status"] == "absent"


class TestDropRecordEmbeddings:
    def test_drop_clears_table_sidecar_and_space(self, dataset_with_embeddings: Dataset):
        dataset_with_embeddings.drop_record_embeddings()
        assert not dataset_with_embeddings.has_record_embeddings()
        assert not (dataset_with_embeddings.path / "embeddings.json").exists()
        assert not _embeddings_table_dir(dataset_with_embeddings).exists()
        assert dataset_with_embeddings.record_embedding_health()["status"] == "absent"

    def test_drop_is_safe_when_the_table_is_already_gone(self, dataset_with_embeddings: Dataset):
        shutil.rmtree(_embeddings_table_dir(dataset_with_embeddings))
        dataset_with_embeddings.drop_record_embeddings()  # must not raise
        assert not dataset_with_embeddings.has_record_embeddings()

    def test_recompute_after_drop_works(self, dataset_with_embeddings: Dataset):
        dataset_with_embeddings.drop_record_embeddings()
        dataset_with_embeddings.create_record_embedding_table(dim=4, model_id="new-model")
        dataset_with_embeddings.add_record_embeddings(
            [{"record_id": f"r{i}", "vector": _bit_vector(i, dim=4)} for i in range(20)]
        )
        health = dataset_with_embeddings.record_embedding_health()
        assert health["status"] == "ready"
        assert health["model_id"] == "new-model"
        assert health["dim"] == 4
