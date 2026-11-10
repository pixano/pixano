# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Record-level embedding storage + vector search (no ML model involved)."""

import json
import shutil
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
from s3path import S3Path

from pixano.datasets.dataset import _UNREAD, Dataset, _file_stamp
from pixano.datasets.dataset_features_values import DatasetFeaturesValues
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.embedding_spaces import FORMAT_VERSION, AmbiguousModelError
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
        # Broken rather than absent: no computation may rewrite the file, a recomputation from nothing does.
        assert reopened.record_embedding_health()["status"] == "corrupt"


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
    """An embedding belongs to a medium, and a record may hold several."""

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
        """Rows written per record, before, inflated the count to "ready"."""
        six_cameras.drop_record_embeddings()
        six_cameras.create_record_embedding_table(dim=8, model_id="test-clip", metric="cosine")
        six_cameras.add_record_embeddings(
            [{"record_id": f"r{i}", "vector": _bit_vector(i + 1)} for i in range(10)]
            + [{"record_id": "r0", "view_id": f"r0-cam{c}", "vector": _bit_vector(c + 1)} for c in range(6)] * 10
        )

        health = six_cameras.record_embedding_health()

        assert (health["status"], health["embedded_media"], health["media"]) == ("partial", 6, 60)

    def test_a_prefilter_smaller_than_k_does_not_widen_to_the_whole_table(self, six_cameras: Dataset):
        """With fewer than k records to find, the search widened up to the table."""
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


# A table large enough to train a vector index, in vectors of a modest dimension: the property
# checked is the search's re-ranking, not the speed an index buys.
INDEXED_RECORDS = 2_000
INDEXED_DIM = 32
NEAREST = 10
QUERIES = 20

# The share of the exact nearest records a search through the index must find. An index's training
# is random, and a search reads only some of its partitions, so even re-ranked it can miss one now
# and then: over 30 builds of this fixture it found 99.0% to 100% of them, against 41% at best
# without re-ranking. The floor sits between, far from both.
RECALL_FLOOR = 0.95


@pytest.fixture()
def indexed_dataset() -> tuple[Dataset, np.ndarray]:
    """Records whose vectors gather around a few directions, as images around their subjects, indexed IVF_PQ."""
    rng = np.random.default_rng(7)
    directions = rng.standard_normal((20, INDEXED_DIM))
    vectors = directions[rng.integers(0, 20, INDEXED_RECORDS)] + rng.normal(0.0, 0.3, (INDEXED_RECORDS, INDEXED_DIM))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    tmp = Path(tempfile.mkdtemp()) / "indexed"
    dataset = Dataset.create(tmp, DatasetInfo(name="indexed", description="d", record=Record, views={"image": Image}))
    dataset.add_records({"records": [Record(id=f"r{i}") for i in range(INDEXED_RECORDS)]})
    dataset.create_record_embedding_table(dim=INDEXED_DIM, model_id="test-clip", metric="cosine")
    dataset.add_record_embeddings(
        [{"record_id": f"r{i}", "view_id": f"img-r{i}", "vector": vectors[i].tolist()} for i in range(INDEXED_RECORDS)]
    )
    dataset.build_record_embedding_index()
    assert [index.index_type for index in dataset.open_table("embeddings").list_indices() if "vector" in index.columns]
    return dataset, vectors


class TestSearchThroughAVectorIndex:
    def test_it_finds_the_exact_nearest_records(self, indexed_dataset: tuple[Dataset, np.ndarray]):
        """A quantised index ranks roughly: read without re-ranking, IVF_PQ found 38% of them here."""
        dataset, vectors = indexed_dataset
        rng = np.random.default_rng(11)
        found = 0
        for query in vectors[rng.integers(0, INDEXED_RECORDS, QUERIES)]:
            exact = {f"r{i}" for i in np.argsort(vectors @ query)[::-1][:NEAREST]}

            records, _ = dataset.search_records(query.tolist(), k=NEAREST)

            found += len(exact & {record.id for record in records})
        assert found / (QUERIES * NEAREST) >= RECALL_FLOOR


# The second model's dimension: five bits tell the twenty records apart, where four would give two
# of them the same vector.
SIGLIP_DIM = 5
# What a dataset's files are given, so that the application and a worker running as two users share them.
SHARED_PERMISSIONS = 0o644
# A narrower choice of the deployer's, which a rewrite must not undo.
GROUP_PERMISSIONS = 0o640
# A file only its owner reads.
OWNER_ONLY_PERMISSIONS = 0o600


def _two_model_dataset() -> tuple[Dataset, dict[str, Any], dict[str, Any]]:
    """Twenty records, each image embedded by two models: `test-clip` in 8 dimensions, `test-siglip` in 5.

    Returns:
        The dataset, and its two spaces: clip's, the default, then siglip's.
    """
    tmp = Path(tempfile.mkdtemp()) / "two_models"
    dataset = Dataset.create(tmp, DatasetInfo(name="two", description="d", record=Record, views={"image": Image}))
    dataset.add_records({"records": [Record(id=f"r{i}") for i in range(20)]})
    dataset.add_data("images", [_image(f"img-r{i}", f"r{i}") for i in range(20)], raise_or_warn="none")
    clip = dataset.ensure_record_embedding_space("test-clip", "ckpt-a", dim=8)
    dataset.add_record_embeddings(
        [{"record_id": f"r{i}", "view_id": f"img-r{i}", "vector": _bit_vector(i)} for i in range(20)], clip["id"]
    )
    siglip = dataset.ensure_record_embedding_space("test-siglip", "ckpt-b", dim=SIGLIP_DIM)
    # The second model sees the records the other way round.
    dataset.add_record_embeddings(
        [
            {"record_id": f"r{i}", "view_id": f"img-r{i}", "vector": _bit_vector(19 - i, dim=SIGLIP_DIM)}
            for i in range(20)
        ],
        siglip["id"],
    )
    return dataset, clip, siglip


def _rewrite(dataset: Dataset, change: Callable[[dict[str, Any]], None]) -> Dataset:
    """Change `embeddings.json` as another build, or a person, would; the dataset opened anew."""
    sidecar = dataset.path / "embeddings.json"
    document = json.loads(sidecar.read_text())
    change(document)
    sidecar.write_text(json.dumps(document))
    return Dataset(dataset.path)


class TestSeveralModels:
    """One table per model: two models' vectors side by side, each searched in its own space."""

    def test_each_model_has_its_space_the_first_one_the_default(self):
        dataset, clip, siglip = _two_model_dataset()

        spaces = dataset.record_embedding_spaces()

        assert [(space["model_id"], space["dim"], space["default"]) for space in spaces] == [
            ("test-clip", 8, True),
            ("test-siglip", SIGLIP_DIM, False),
        ]
        assert clip["table"] == "embeddings"
        assert siglip["table"] == f"embeddings_{siglip['id']}"
        assert dataset.open_table(siglip["table"]).count_rows() == 20

    def test_a_search_reads_the_model_it_names(self):
        dataset, _, siglip = _two_model_dataset()

        by_clip, _ = dataset.search_records(_bit_vector(3), k=1, model="test-clip")
        by_siglip, _ = dataset.search_records(_bit_vector(3, dim=SIGLIP_DIM), k=1, model="test-siglip")
        by_id, _ = dataset.search_records(_bit_vector(3, dim=SIGLIP_DIM), k=1, model=siglip["id"])
        by_default, _ = dataset.search_records(_bit_vector(3), k=1)

        assert (by_clip[0].id, by_default[0].id) == ("r3", "r3")
        # r16 is the record siglip placed at 3 (19 - 16).
        assert (by_siglip[0].id, by_id[0].id) == ("r16", "r16")

    def test_a_model_the_dataset_holds_no_embeddings_of_is_refused(self):
        dataset, _, _ = _two_model_dataset()

        with pytest.raises(DatasetAccessError, match="no embeddings of model 'dinov2'"):
            dataset.search_records(_bit_vector(3), k=1, model="dinov2")

    def test_the_same_model_keeps_its_space_and_its_vectors(self):
        dataset, clip, _ = _two_model_dataset()

        again = dataset.ensure_record_embedding_space("test-clip", "ckpt-a", dim=8)

        assert again == clip
        assert dataset.open_table(clip["table"]).count_rows() == 20

    def test_recomputing_a_model_from_nothing_empties_only_its_table_and_leaves_the_default(self):
        dataset, clip, siglip = _two_model_dataset()

        recomputed = dataset.create_record_embedding_table(dim=SIGLIP_DIM, model_id="test-siglip", checkpoint="ckpt-b")

        assert recomputed["table"] == siglip["table"]
        assert dataset.open_table(recomputed["table"]).count_rows() == 0
        assert dataset.open_table(clip["table"]).count_rows() == 20
        assert dataset.record_embedding_space()["id"] == clip["id"]

    def test_recomputing_the_default_model_keeps_it_the_default(self):
        dataset, _, _ = _two_model_dataset()

        recomputed = dataset.create_record_embedding_table(dim=8, model_id="test-clip", checkpoint="ckpt-a")

        assert dataset.record_embedding_space()["id"] == recomputed["id"]
        assert dataset.open_table(recomputed["table"]).count_rows() == 0

    def test_recomputing_a_model_that_does_not_tell_its_checkpoint_keeps_the_other_names(self):
        dataset, _, siglip = _two_model_dataset()

        recomputed = dataset.create_record_embedding_table(dim=8, model_id="test-clip")

        assert (recomputed["checkpoint"], dataset.open_table(recomputed["table"]).count_rows()) == ("", 0)
        assert dataset.open_table(siglip["table"]).count_rows() == 20

    def test_another_checkpoint_of_a_name_is_another_space(self):
        dataset, _, _ = _two_model_dataset()

        dataset.ensure_record_embedding_space("test-clip", "ckpt-c", dim=8)

        assert [space["checkpoint"] for space in dataset.record_embedding_spaces()] == ["ckpt-a", "ckpt-b", "ckpt-c"]

    def test_the_very_model_at_another_dimension_is_refused(self):
        dataset, _, _ = _two_model_dataset()

        with pytest.raises(DatasetAccessError, match="of dimension 8, not 16"):
            dataset.ensure_record_embedding_space("test-clip", "ckpt-a", dim=16)

    def test_dropping_one_model_leaves_the_other_and_hands_it_the_default(self):
        dataset, clip, _ = _two_model_dataset()

        dataset.drop_record_embeddings(clip["id"])

        assert clip["table"] not in dataset._db_connection.list_tables().tables
        reopened = Dataset(dataset.path)
        assert [space["model_id"] for space in reopened.record_embedding_spaces()] == ["test-siglip"]
        assert reopened.record_embedding_space()["model_id"] == "test-siglip"

    def test_a_model_known_by_its_name_and_checkpoint_empties_its_own_embeddings_only(self):
        """Its space keeps its id, its place and the default; only its vectors go."""
        dataset, clip, siglip = _two_model_dataset()

        emptied = dataset.empty_model_record_embeddings("test-siglip", "ckpt-b", index_type="IVF_SQ")

        assert (emptied["id"], emptied["table"], emptied["index_type"]) == (siglip["id"], siglip["table"], "IVF_SQ")
        reopened = Dataset(dataset.path)
        assert [space["id"] for space in reopened.record_embedding_spaces()] == [clip["id"], siglip["id"]]
        assert reopened.record_embedding_space()["id"] == clip["id"]
        assert reopened.open_table(siglip["table"]).count_rows() == 0
        assert reopened.open_table(clip["table"]).count_rows() == 20

    def test_emptying_the_default_model_leaves_it_the_default(self):
        dataset, clip, _ = _two_model_dataset()

        dataset.empty_model_record_embeddings("test-clip", "ckpt-a")

        assert Dataset(dataset.path).record_embedding_space()["id"] == clip["id"]

    def test_a_model_that_does_not_tell_its_checkpoint_never_empties_a_space_that_records_one(self):
        """The weights served now may not be those: the space recorded with its checkpoint is left as it is."""
        dataset, clip, _ = _two_model_dataset()

        with pytest.raises(AmbiguousModelError, match="ckpt-a"):
            dataset.empty_model_record_embeddings("test-clip")

        assert dataset.open_table(clip["table"]).count_rows() == 20
        assert dataset.empty_model_record_embeddings("test-dinov2") is None

    def test_a_model_that_does_not_tell_its_checkpoint_empties_the_space_recorded_without_one(self):
        dataset, _, _ = _two_model_dataset()
        untold = dataset.ensure_record_embedding_space("test-dinov2", "", dim=8)
        dataset.add_record_embeddings(
            [{"record_id": "r1", "view_id": "img-r1", "vector": _bit_vector(1)}], untold["id"]
        )

        emptied = dataset.empty_model_record_embeddings("test-dinov2")

        assert emptied["id"] == untold["id"]
        assert dataset.open_table(untold["table"]).count_rows() == 0

    def test_a_model_a_process_recorded_meanwhile_is_found_and_emptied(self):
        dataset, _, _ = _two_model_dataset()
        Dataset(dataset.path).upsert_record_embeddings(
            "test-dinov2", "vitb14", [{"id": "d1", "record_id": "r1", "view_id": "img-r1", "vector": _bit_vector(1)}]
        )

        emptied = dataset.empty_model_record_embeddings("test-dinov2", "vitb14")

        assert emptied is not None
        assert dataset.open_table(emptied["table"]).count_rows() == 0

    def test_dropping_a_space_the_dataset_does_not_hold_leaves_it_as_it_is(self):
        dataset, _, _ = _two_model_dataset()
        sidecar = dataset.path / "embeddings.json"
        before = sidecar.read_text()

        dataset.drop_record_embeddings("dinov2-00000000")

        assert sidecar.read_text() == before
        assert len(dataset.record_embedding_spaces()) == 2

    def test_a_writer_names_a_space_by_its_id_and_never_by_an_empty_one(self):
        dataset, _, _ = _two_model_dataset()

        with pytest.raises(ValueError):
            dataset.drop_record_embeddings("")
        with pytest.raises(ValueError):
            dataset.add_record_embeddings([{"record_id": "r1", "vector": _bit_vector(1)}], "")
        with pytest.raises(ValueError):
            dataset.set_default_record_embedding_space("")
        with pytest.raises(DatasetAccessError, match="no embedding space 'test-siglip'"):
            dataset.set_default_record_embedding_space("test-siglip")

    def test_dropping_every_model_drops_the_tables_a_broken_description_no_longer_names(self):
        dataset, _, _ = _two_model_dataset()
        (dataset.path / "embeddings.json").write_text("{")
        broken = Dataset(dataset.path)
        assert not broken.has_record_embeddings()

        broken.drop_record_embeddings()

        tables = broken._db_connection.list_tables().tables
        assert not [name for name in tables if name.startswith("embeddings")]
        assert {"records", "images"} <= set(tables)
        assert not (dataset.path / "embeddings.json").exists()

    def test_dropping_every_model_leaves_a_table_info_json_declares_whatever_its_name(self):
        dataset, _, _ = _two_model_dataset()
        declared = "embeddings_declared"
        dataset._db_connection.create_table(declared, schema=dataset.open_table("records").schema)
        dataset.info.tables[declared] = Record

        dataset.drop_record_embeddings()

        assert declared in dataset._db_connection.list_tables().tables

    def test_a_table_that_cannot_be_dropped_is_no_space_of_the_dataset_any_more(self, mocker):
        dataset, clip, _ = _two_model_dataset()
        mocker.patch.object(type(dataset._db_connection), "drop_table", side_effect=RuntimeError("corrupt"))

        dataset.drop_record_embeddings(clip["id"])

        assert [space["model_id"] for space in Dataset(dataset.path).record_embedding_spaces()] == ["test-siglip"]

    def test_another_model_can_be_the_default(self):
        dataset, _, siglip = _two_model_dataset()

        dataset.set_default_record_embedding_space(siglip["id"])

        assert Dataset(dataset.path).record_embedding_space()["model_id"] == "test-siglip"
        assert not dataset.is_stale()

    def test_health_is_each_models(self):
        dataset, _, _ = _two_model_dataset()

        health = dataset.record_embedding_health("test-siglip")

        assert (health["status"], health["model_id"], health["dim"], health["embedded_media"]) == (
            "ready",
            "test-siglip",
            SIGLIP_DIM,
            20,
        )
        assert dataset.record_embedding_health("dinov2")["status"] == "absent"

    def test_a_model_another_process_adds_makes_the_dataset_stale(self):
        dataset, _, _ = _two_model_dataset()
        assert not dataset.is_stale()

        Dataset(dataset.path).ensure_record_embedding_space("test-dinov2", "vitb14", dim=8)

        assert dataset.is_stale()
        assert len(Dataset(dataset.path).record_embedding_spaces()) == 3

    def test_the_last_models_embeddings_another_process_drops_make_the_dataset_stale(self):
        dataset, _, _ = _two_model_dataset()

        Dataset(dataset.path).drop_record_embeddings()

        assert dataset.is_stale()

    def test_a_write_keeps_the_spaces_another_process_added_meanwhile(self):
        dataset, clip, _ = _two_model_dataset()
        Dataset(dataset.path).ensure_record_embedding_space("test-dinov2", "vitb14", dim=8)

        # This instance still holds two spaces: its writes start from the file, not from them.
        dataset.ensure_record_embedding_space("test-other", "v1", dim=8)
        dataset.drop_record_embeddings(clip["id"])

        assert [space["model_id"] for space in Dataset(dataset.path).record_embedding_spaces()] == [
            "test-siglip",
            "test-dinov2",
            "test-other",
        ]

    def test_a_write_after_info_json_changed_never_hides_the_embeddings_tables_from_a_reader(self, mocker):
        dataset, clip, siglip = _two_model_dataset()
        other = Dataset(dataset.path)
        with other.write_lock():
            other._patch_info_json({"description": "changed by another process"})
        declared_meanwhile: list[bool] = []
        read = DatasetFeaturesValues.from_json

        def reading(path: Path) -> DatasetFeaturesValues:
            # What a search on another thread sees while this write refreshes the dataset.
            declared_meanwhile.append(clip["table"] in dataset.info.tables)
            return read(path)

        mocker.patch.object(DatasetFeaturesValues, "from_json", side_effect=reading)

        dataset.set_default_record_embedding_space(siglip["id"])

        assert declared_meanwhile and all(declared_meanwhile)
        assert dataset.info.description == "changed by another process"
        assert {clip["table"], siglip["table"]} <= set(dataset.info.tables)

    def test_a_space_whose_table_went_missing_gets_an_empty_one_back(self):
        dataset, _, siglip = _two_model_dataset()
        dataset._db_connection.drop_table(siglip["table"])

        dataset.ensure_record_embedding_space("test-siglip", "ckpt-b", dim=SIGLIP_DIM)

        assert dataset.open_table(siglip["table"]).count_rows() == 0

    def test_deleting_a_record_deletes_its_vectors_of_every_model(self):
        dataset, clip, siglip = _two_model_dataset()

        dataset.delete_records(["r3"])

        for space in (clip, siglip):
            assert dataset.open_table(space["table"]).count_rows("record_id = 'r3'") == 0
            assert dataset.open_table(space["table"]).count_rows() == 19


class TestWritingAModelsVectors:
    """A writer that knows its model, not its space: found or created, and written, under one lock."""

    @staticmethod
    def _rows(*indexes: int, dim: int = 8) -> list[dict[str, Any]]:
        return [
            {"id": f"e-r{i}", "record_id": f"r{i}", "view_id": f"img-r{i}", "vector": _bit_vector(i, dim=dim)}
            for i in indexes
        ]

    def test_creates_the_space_and_replaces_rows_by_id(self):
        dataset, _, _ = _two_model_dataset()

        dataset.upsert_record_embeddings("test-dinov2", "vitb14", self._rows(1, 2))
        space = dataset.upsert_record_embeddings("test-dinov2", "vitb14", self._rows(2, 3))

        assert space["model_id"] == "test-dinov2"
        assert dataset.open_table(space["table"]).count_rows() == 3

    def test_a_space_another_process_deleted_is_created_again_not_written_from_what_was_read(self):
        """The writer's instance still holds the space: written into from it, the rows would land nowhere."""
        dataset, _, siglip = _two_model_dataset()
        Dataset(dataset.path).drop_record_embeddings(siglip["id"])

        space = dataset.upsert_record_embeddings("test-siglip", "ckpt-b", self._rows(1, dim=SIGLIP_DIM))

        assert dataset.open_table(space["table"]).count_rows() == 1
        assert [s["model_id"] for s in Dataset(dataset.path).record_embedding_spaces()] == [
            "test-clip",
            "test-siglip",
        ]

    def test_a_space_another_process_created_is_written_into_not_created_twice(self):
        dataset, _, _ = _two_model_dataset()
        Dataset(dataset.path).upsert_record_embeddings("test-dinov2", "vitb14", self._rows(1))

        space = dataset.upsert_record_embeddings("test-dinov2", "vitb14", self._rows(2))

        assert dataset.open_table(space["table"]).count_rows() == 2
        assert len(Dataset(dataset.path).record_embedding_spaces()) == 3

    def test_a_writer_that_does_not_tell_its_checkpoint_never_guesses_between_two(self):
        dataset, _, _ = _two_model_dataset()
        dataset.ensure_record_embedding_space("test-clip", "ckpt-c", dim=8)

        with pytest.raises(AmbiguousModelError, match="ckpt-a, ckpt-c"):
            dataset.upsert_record_embeddings("test-clip", "", self._rows(1))
        with pytest.raises(AmbiguousModelError):
            dataset.empty_model_record_embeddings("test-clip")
        with pytest.raises(AmbiguousModelError):
            dataset.create_record_embedding_table(dim=8, model_id="test-clip")

    def test_a_writer_that_does_not_tell_its_checkpoint_writes_into_the_one_space_of_its_name(self):
        dataset, clip, _ = _two_model_dataset()

        space = dataset.upsert_record_embeddings("test-clip", "", self._rows(1))

        assert space["id"] == clip["id"]

    def test_no_row_is_refused(self):
        dataset, _, _ = _two_model_dataset()

        with pytest.raises(ValueError, match="No vector"):
            dataset.upsert_record_embeddings("test-clip", "ckpt-a", [])


class TestTheEmbeddingsFile:
    """`embeddings.json`: the document a build before several models reads, while it can; replaced whole."""

    def test_a_dataset_of_one_model_keeps_the_document_it_always_had(self):
        dataset, clip, siglip = _two_model_dataset()
        sidecar = dataset.path / "embeddings.json"
        assert json.loads(sidecar.read_text())["version"] == FORMAT_VERSION

        dataset.drop_record_embeddings(siglip["id"])

        document = json.loads(sidecar.read_text())
        assert "spaces" not in document
        assert (document["table"], document["model_id"], document["dim"], document["id"]) == (
            "embeddings",
            "test-clip",
            8,
            clip["id"],
        )

    def test_written_for_the_first_time_it_gets_the_permissions_of_any_new_file(self):
        tmp = Path(tempfile.mkdtemp()) / "fresh"
        dataset = Dataset.create(tmp, DatasetInfo(name="f", description="d", record=Record, views={"image": Image}))
        # Not those of another file of the dataset: a file narrowed to its owner stays so.
        dataset._info_file.chmod(OWNER_ONLY_PERMISSIONS)
        probe = dataset.path / "probe"
        probe.write_text("")

        dataset.ensure_record_embedding_space("test-clip", "ckpt-a", dim=8)

        written = stat.S_IMODE((dataset.path / "embeddings.json").stat().st_mode)
        assert written == stat.S_IMODE(probe.stat().st_mode)

    def test_rewritten_it_keeps_its_permissions(self):
        dataset, _, siglip = _two_model_dataset()
        sidecar = dataset.path / "embeddings.json"
        sidecar.chmod(GROUP_PERMISSIONS)

        dataset.set_default_record_embedding_space(siglip["id"])

        assert stat.S_IMODE(sidecar.stat().st_mode) == GROUP_PERMISSIONS
        assert not list(dataset.path.glob("embeddings.json.*.tmp"))

    def test_on_an_object_store_it_is_written_whole(self, mocker):
        dataset, _, siglip = _two_model_dataset()
        written: list[str] = []
        mocker.patch.object(S3Path, "write_text", side_effect=lambda content, encoding: written.append(content))
        mocker.patch.object(S3Path, "stat", side_effect=AssertionError("an object store has no stat"))
        dataset._embeddings_file = S3Path("/bucket/two_models/embeddings.json")

        dataset._save_embedding_spaces(dataset._embedding_spaces.with_default(siglip["id"]))

        assert json.loads(written[0])["default"] == siglip["id"]
        assert dataset.record_embedding_space()["id"] == siglip["id"]

    def test_on_an_object_store_a_write_starts_from_the_file_not_from_what_was_read_before(self, mocker):
        dataset, _, _ = _two_model_dataset()
        stored = json.loads((dataset.path / "embeddings.json").read_text())
        added = {**stored["spaces"][1], "id": "dinov2-00000000", "table": "embeddings_dinov2-00000000"}
        stored["spaces"].append({**added, "model_id": "test-dinov2"})
        mocker.patch.object(S3Path, "is_file", return_value=True)
        mocker.patch.object(S3Path, "read_bytes", return_value=json.dumps(stored).encode())
        dataset._embeddings_file = S3Path("/bucket/two_models/embeddings.json")

        spaces = dataset._writable_spaces()

        assert [space.model_id for space in spaces.spaces] == ["test-clip", "test-siglip", "test-dinov2"]


class TestADescriptionThisBuildCannotReadEntirely:
    """A space left out, or a later version: the description is not rewritten, so that nothing it names is lost."""

    @pytest.fixture()
    def damaged(self) -> tuple[Dataset, dict[str, Any]]:
        dataset, clip, _ = _two_model_dataset()
        return _rewrite(dataset, lambda document: document["spaces"][0].update(dim="eight")), clip

    def test_reads_what_it_can(self, damaged: tuple[Dataset, dict[str, Any]]):
        dataset, _ = damaged

        assert [space["model_id"] for space in dataset.record_embedding_spaces()] == ["test-siglip"]

    @pytest.mark.parametrize(
        "write",
        [
            lambda dataset: dataset.ensure_record_embedding_space("test-dinov2", "vitb14", dim=8),
            lambda dataset: dataset.create_record_embedding_table(dim=8, model_id="test-dinov2"),
            lambda dataset: dataset.set_default_record_embedding_space(dataset.record_embedding_space()["id"]),
            lambda dataset: dataset.drop_record_embeddings(dataset.record_embedding_space()["id"]),
            lambda dataset: dataset.empty_model_record_embeddings("test-siglip", "ckpt-b"),
        ],
        ids=["ensure", "create", "set_default", "drop_one", "empty_model"],
    )
    def test_refuses_to_rewrite_it(self, damaged: tuple[Dataset, dict[str, Any]], write: Callable[[Dataset], Any]):
        dataset, clip = damaged
        before = (dataset.path / "embeddings.json").read_text()

        with pytest.raises(DatasetAccessError, match="cannot be read entirely"):
            write(dataset)

        assert (dataset.path / "embeddings.json").read_text() == before
        # The space left out is no table of the dataset's any more, but its vectors are all there.
        assert dataset._db_connection.open_table(clip["table"]).count_rows() == 20

    def test_deleting_every_models_embeddings_starts_again(self, damaged: tuple[Dataset, dict[str, Any]]):
        dataset, _ = damaged

        dataset.drop_record_embeddings()
        dataset.ensure_record_embedding_space("test-dinov2", "vitb14", dim=8)

        assert [space["model_id"] for space in Dataset(dataset.path).record_embedding_spaces()] == ["test-dinov2"]

    def test_one_of_a_later_version_is_read_and_not_rewritten(self):
        dataset, _, _ = _two_model_dataset()

        later = _rewrite(dataset, lambda document: document.update(version=FORMAT_VERSION + 1))

        assert len(later.record_embedding_spaces()) == 2
        with pytest.raises(DatasetAccessError, match="cannot be read entirely"):
            later.ensure_record_embedding_space("test-dinov2", "vitb14", dim=8)

    def test_what_it_does_not_know_is_written_back_as_it_was(self):
        dataset, _, siglip = _two_model_dataset()

        def add_unknown(document: dict[str, Any]) -> None:
            document["written_by"] = "a later build"
            document["spaces"][1]["normalised"] = True

        reopened = _rewrite(dataset, add_unknown)
        reopened.set_default_record_embedding_space(siglip["id"])

        document = json.loads((dataset.path / "embeddings.json").read_text())
        assert (document["written_by"], document["spaces"][1]["normalised"]) == ("a later build", True)

    def test_a_space_naming_a_table_not_its_own_is_left_out(self):
        dataset, _, _ = _two_model_dataset()

        reopened = _rewrite(dataset, lambda document: document["spaces"][1].update(table="records"))

        assert [space["model_id"] for space in reopened.record_embedding_spaces()] == ["test-clip"]
        assert issubclass(reopened.info.tables["records"], Record)

    def test_a_file_that_is_not_utf8_leaves_the_dataset_open_and_its_embeddings_broken(self):
        dataset, _, _ = _two_model_dataset()
        (dataset.path / "embeddings.json").write_bytes(b"\xff\xfe{")

        reopened = Dataset(dataset.path)

        assert not reopened.has_record_embeddings()
        assert not reopened.record_embeddings_fully_read()
        assert reopened.record_embedding_health()["status"] == "corrupt"

    def test_a_file_that_cannot_be_examined_stamps_the_dataset_unread(self):
        dataset, _, _ = _two_model_dataset()

        with patch.object(type(dataset._embeddings_file), "stat", side_effect=PermissionError("denied")):
            assert _file_stamp(dataset._embeddings_file) is _UNREAD

    def test_a_file_that_cannot_be_opened_keeps_the_spaces_held_and_the_dataset_stale(self):
        dataset, _, _ = _two_model_dataset()

        with patch.object(type(dataset._embeddings_file), "read_bytes", side_effect=PermissionError("denied")):
            dataset._load_record_embedding_spaces()

        assert len(dataset.record_embedding_spaces()) == 2
        assert dataset.is_stale()
        with pytest.raises(DatasetAccessError, match="cannot be read entirely"):
            dataset._writable_spaces()


class TestEmbeddingsWrittenBeforeSeveralModels:
    """A dataset whose `embeddings.json` describes its one model at the top level, as it was written."""

    @pytest.fixture()
    def legacy(self, dataset_with_embeddings: Dataset) -> Dataset:
        sidecar = dataset_with_embeddings.path / "embeddings.json"
        sidecar.write_text(
            json.dumps(
                {
                    "table": "embeddings",
                    "model_id": "test-clip",
                    "dim": 8,
                    "metric": "cosine",
                    "source_view": "image",
                    "index_type": "IVF_PQ",
                }
            )
        )
        return Dataset(dataset_with_embeddings.path)

    def test_serves_the_callers_of_one_model_as_it_did(self, legacy: Dataset):
        records, _ = legacy.search_records(_bit_vector(5), k=1)

        assert records[0].id == "r5"
        assert legacy.open_table("embeddings").count_rows() == 20
        assert legacy.record_embedding_health()["status"] == "ready"

        legacy.drop_record_embeddings()

        assert not (legacy.path / "embeddings.json").exists()
        assert "embeddings" not in legacy._db_connection.list_tables().tables

    def test_its_model_learning_its_checkpoint_keeps_the_document_and_the_vectors(self, legacy: Dataset):
        legacy.ensure_record_embedding_space("test-clip", "ckpt-a", dim=8)

        document = json.loads((legacy.path / "embeddings.json").read_text())
        assert "spaces" not in document
        assert (document["table"], document["checkpoint"]) == ("embeddings", "ckpt-a")
        assert legacy.open_table("embeddings").count_rows() == 20

    def test_another_model_beside_it_rewrites_the_file_in_the_new_format(self, legacy: Dataset):
        legacy.ensure_record_embedding_space("test-siglip", "ckpt-b", dim=SIGLIP_DIM)

        document = json.loads((legacy.path / "embeddings.json").read_text())
        assert document["version"] == FORMAT_VERSION
        assert [space["model_id"] for space in document["spaces"]] == ["test-clip", "test-siglip"]

    def test_its_name_at_another_dimension_is_another_model(self, legacy: Dataset):
        other = legacy.ensure_record_embedding_space("test-clip", "ViT-L-14", dim=16)

        assert other["table"] != "embeddings"
        assert len(Dataset(legacy.path).record_embedding_spaces()) == 2
        assert legacy.open_table("embeddings").count_rows() == 20

    def test_its_name_at_another_dimension_recomputed_from_nothing_never_takes_its_id(self, legacy: Dataset):
        """It keeps the id of a space without a checkpoint once it learns its own; a new one gets another."""
        learnt = legacy.ensure_record_embedding_space("test-clip", "ckpt-a", dim=8)

        recomputed = legacy.create_record_embedding_table(dim=16, model_id="test-clip")

        assert recomputed["id"] != learnt["id"]
        assert [space["id"] for space in legacy.record_embedding_spaces()] == [learnt["id"], recomputed["id"]]
        assert legacy.open_table(learnt["table"]).count_rows() == 20
