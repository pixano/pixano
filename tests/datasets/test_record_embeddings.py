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


def _image(image_id: str, record_id: str, name: str = "image") -> Image:
    return Image(id=image_id, record_id=record_id, logical_name=name, uri=f"{image_id}.jpg", width=8, height=8)


@pytest.fixture()
def dataset_with_embeddings() -> Dataset:
    tmp = Path(tempfile.mkdtemp()) / "ds"
    dataset = Dataset.create(tmp, DatasetInfo(name="emb", description="d", record=Record, views={"image": Image}))
    dataset.add_records({"records": [Record(id=f"r{i}") for i in range(20)]})
    dataset.add_data("images", [_image(f"img-r{i}", f"r{i}") for i in range(20)], raise_or_warn="none")
    dataset.create_record_embedding_table(dim=8, model_id="test-clip", metric="cosine")
    dataset.add_record_embeddings(
        [{"record_id": f"r{i}", "view_id": f"img-r{i}", "vector": _bit_vector(i)} for i in range(20)]
    )
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

    def test_partial_when_some_media_have_no_vector(self, dataset_with_embeddings: Dataset):
        dataset_with_embeddings.add_records({"records": [Record(id="extra")]})
        dataset_with_embeddings.add_data("images", [_image("img-extra", "extra")], raise_or_warn="none")
        health = dataset_with_embeddings.record_embedding_health()
        assert health["status"] == "partial"
        assert (health["rows"], health["media"], health["records"]) == (20, 21, 21)

    def test_a_record_without_media_does_not_make_it_partial(self, dataset_with_embeddings: Dataset):
        """nuScenes' lidar sweeps hold no image: counting records kept the table "partial" for ever."""
        dataset_with_embeddings.add_records({"records": [Record(id="lidar-only")]})

        assert dataset_with_embeddings.record_embedding_health()["status"] == "ready"

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
            [{"record_id": f"r{i}", "view_id": f"img-r{i}", "vector": _bit_vector(i, dim=4)} for i in range(20)]
        )
        health = dataset_with_embeddings.record_embedding_health()
        assert health["status"] == "ready"
        assert health["model_id"] == "new-model"
        assert health["dim"] == 4


class TestMultiMediaRecords:
    """Step 2, lot 1: an embedding belongs to a medium, and a record may hold several."""

    @pytest.fixture()
    def six_cameras(self) -> Dataset:
        tmp = Path(tempfile.mkdtemp()) / "cams"
        dataset = Dataset.create(tmp, DatasetInfo(name="cams", description="d", record=Record, views={"image": Image}))
        dataset.add_records({"records": [Record(id=f"r{i}") for i in range(10)]})
        cameras = [_image(f"r{i}-cam{c}", f"r{i}", f"cam{c}") for i in range(10) for c in range(6)]
        dataset.add_data("images", cameras, raise_or_warn="none")
        dataset.create_record_embedding_table(dim=8, model_id="test-clip", metric="cosine")
        dataset.add_record_embeddings(
            [
                {"record_id": f"r{i}", "view_id": f"r{i}-cam{c}", "vector": _bit_vector(i * 6 + c + 1)}
                for i in range(10)
                for c in range(6)
            ]
        )
        return dataset

    def test_k_records_are_found_although_each_has_six_vectors(self, six_cameras: Dataset):
        """Asking for k vectors and grouping by record returned about k / 6 records."""
        records, distances = six_cameras.search_records(_bit_vector(1), k=6)

        assert len({record.id for record in records}) == 6
        assert distances == sorted(distances)

    def test_similar_to_a_record_uses_its_closest_medium(self, six_cameras: Dataset):
        own_vectors = [_bit_vector(3 * 6 + c + 1) for c in range(6)]

        records, distances = six_cameras.search_records(own_vectors, k=1)

        assert (records[0].id, distances[0]) == ("r3", pytest.approx(0.0, abs=1e-6))

    def test_rows_that_name_no_medium_do_not_make_it_ready(self, six_cameras: Dataset):
        """Review of step 2, lot 1: rows written per record, before, inflated the count to "ready"."""
        six_cameras.drop_record_embeddings()
        six_cameras.create_record_embedding_table(dim=8, model_id="test-clip", metric="cosine")
        six_cameras.add_record_embeddings(
            [{"record_id": f"r{i}", "vector": _bit_vector(i + 1)} for i in range(10)]
            + [{"record_id": "r0", "view_id": f"r0-cam{c}", "vector": _bit_vector(c + 1)} for c in range(6)] * 10
        )

        health = six_cameras.record_embedding_health()

        assert (health["status"], health["embedded_media"], health["media"]) == ("partial", 6, 60)

    def test_a_prefilter_smaller_than_k_does_not_widen_to_the_whole_table(self, six_cameras: Dataset):
        """Review of step 2, lot 1: with fewer than k records to find, the search widened up to the table."""
        searches: list[int] = []
        table = six_cameras.open_table(six_cameras._RECORD_EMBEDDING_TABLE)
        real_search = table.search

        def counting_search(*args, **kwargs):
            searches.append(1)
            return real_search(*args, **kwargs)

        table.search = counting_search  # type: ignore[method-assign]
        six_cameras._table_handles[six_cameras._RECORD_EMBEDDING_TABLE] = table

        records, _ = six_cameras.search_records(_bit_vector(1), k=50, record_id_filter=["r1", "r2"])

        assert {record.id for record in records} == {"r1", "r2"}
        assert len(searches) == 1

    def test_health_counts_media_not_records(self, six_cameras: Dataset):
        health = six_cameras.record_embedding_health()

        assert (health["status"], health["rows"], health["media"], health["records"]) == ("ready", 60, 60, 10)
