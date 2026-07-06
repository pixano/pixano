# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pyarrow as pa
import pytest

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.schemas import BBox, Entity, Image, Record


def _make_dataset(path: Path) -> Dataset:
    info = DatasetInfo(name="merge_ds", record=Record, entity=Entity, bbox=BBox, views={"image": Image})
    return Dataset.create(path, info)


def _payload() -> dict:
    return {
        "records": Record(id="rec1"),
        "images": Image(
            id="img1", record_id="rec1", logical_name="image", uri="images/1.jpg", width=64, height=48, format="JPEG"
        ),
        "entities": Entity(id="ent1", record_id="rec1"),
        "bboxes": BBox(
            id="box1",
            record_id="rec1",
            entity_id="ent1",
            coords=[0.1, 0.1, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        ),
    }


def _table_counts(dataset: Dataset) -> dict[str, int]:
    return {name: dataset.open_table(name).count_rows() for name in dataset.info.tables}


class TestMergeRecords:
    def test_run_twice_is_idempotent(self, tmp_path: Path):
        dataset = _make_dataset(tmp_path / "ds")

        first = dataset.merge_records(_payload(), check_integrity="raise")
        counts_after_first = _table_counts(dataset)
        second = dataset.merge_records(_payload(), check_integrity="raise")

        assert first == second == {"records": 1, "images": 1, "entities": 1, "bboxes": 1}
        assert (
            _table_counts(dataset)
            == counts_after_first
            == {
                "records": 1,
                "images": 1,
                "entities": 1,
                "bboxes": 1,
            }
        )

    def test_upsert_updates_fields_and_preserves_created_at(self, tmp_path: Path):
        dataset = _make_dataset(tmp_path / "ds")
        dataset.merge_records(_payload(), check_integrity="raise")
        record_created_at_before = dataset.get_data("records")[0].created_at

        updated = _payload()
        updated["bboxes"].confidence = 0.5
        dataset.merge_records(updated, check_integrity="raise")

        boxes = dataset.get_data("bboxes")
        assert len(boxes) == 1
        assert boxes[0].confidence == 0.5

        # Timestamps live on the record table: created_at survives the upsert,
        # updated_at moves forward.
        record = dataset.get_data("records")[0]
        assert record.created_at == record_created_at_before
        assert record.updated_at >= record_created_at_before

    def test_dangling_fk_raises(self, tmp_path: Path):
        dataset = _make_dataset(tmp_path / "ds")
        payload = _payload()
        payload["bboxes"].entity_id = "ghost"

        with pytest.raises(DatasetIntegrityError, match="ghost"):
            dataset.merge_records(payload, check_integrity="raise")

    def test_known_ids_ledger_resolves_fks(self, tmp_path: Path):
        dataset = _make_dataset(tmp_path / "ds")
        dataset.merge_records(_payload(), check_integrity="raise")

        # A later flush referencing only already-imported parents, resolved via the ledger.
        late_box = BBox(
            id="box2",
            record_id="rec1",
            entity_id="ent1",
            coords=[0.3, 0.3, 0.1, 0.1],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        )
        counts = dataset.merge_records(
            {"bboxes": late_box},
            check_integrity="raise",
            known_ids={"records": {"rec1"}, "entities": {"ent1"}},
        )
        assert counts == {"bboxes": 1}
        assert dataset.open_table("bboxes").count_rows() == 2

    def test_arrow_payload_is_validated(self, tmp_path: Path):
        # P3.0 flipped the P0.5 typed refusal: Arrow payloads now validate vectorized.
        dataset = _make_dataset(tmp_path / "ds")
        dangling = pa.record_batch({"id": pa.array(["ent1"]), "record_id": pa.array(["ghost"])})

        with pytest.raises(DatasetIntegrityError, match="ghost"):
            dataset.merge_records({"entities": dangling}, check_integrity="raise")

    def test_arrow_payload_appends_timestamp_columns(self, tmp_path: Path):
        dataset = _make_dataset(tmp_path / "ds")
        arrow_schema = dataset.open_table("records").schema
        subset_schema = pa.schema([f for f in arrow_schema if f.name not in ("created_at", "updated_at")])
        row = Record(id="rec_arrow").model_dump(exclude={"created_at", "updated_at"})
        arrow_table = pa.Table.from_pylist([row], schema=subset_schema)

        counts = dataset.merge_records({"records": arrow_table}, check_integrity="none")

        assert counts == {"records": 1}
        stored = dataset.get_data("records", ids="rec_arrow")
        assert stored is not None
        assert stored.created_at is not None
        assert stored.updated_at is not None

        # Re-merging the same Arrow payload stays idempotent.
        dataset.merge_records({"records": arrow_table}, check_integrity="none")
        assert dataset.open_table("records").count_rows() == 1


class TestCreateScalarIndexes:
    def test_idempotent_index_creation(self, tmp_path: Path):
        dataset = _make_dataset(tmp_path / "ds")
        dataset.merge_records(_payload(), check_integrity="none")

        dataset.create_scalar_indexes()
        dataset.create_scalar_indexes()  # second call must be a no-op

        bbox_indices = list(dataset.open_table("bboxes").list_indices())
        indexed_columns = sorted(column for index in bbox_indices for column in index.columns)
        assert indexed_columns == ["id", "record_id"]

        # Records table has no record_id column: only id is indexed, absent columns skipped.
        record_indices = list(dataset.open_table("records").list_indices())
        assert sorted(column for index in record_indices for column in index.columns) == ["id"]


class TestCacheInvalidation:
    def test_hooks_are_called_and_errors_contained(self):
        calls: list[str] = []

        def hook(dataset_id: str) -> None:
            calls.append(dataset_id)

        def broken_hook(dataset_id: str) -> None:
            raise RuntimeError("boom")

        Dataset.register_cache_invalidation_hook(hook)
        Dataset.register_cache_invalidation_hook(broken_hook)
        try:
            Dataset.invalidate_caches("ds42")
        finally:
            Dataset._cache_invalidation_hooks.remove(hook)
            Dataset._cache_invalidation_hooks.remove(broken_hook)

        assert calls == ["ds42"]

    def test_api_dataset_cache_hook(self):
        from pixano.api.routers import _deps

        _deps._dataset_cache["ds1:/library"] = object()  # type: ignore[assignment]
        _deps._dataset_cache["ds2:/library"] = object()  # type: ignore[assignment]
        try:
            Dataset.invalidate_caches("ds1")
            assert "ds1:/library" not in _deps._dataset_cache
            assert "ds2:/library" in _deps._dataset_cache
        finally:
            _deps._dataset_cache.clear()


class TestValidateBatchFkLookup:
    def test_fk_lookup_override(self, tmp_path: Path):
        from pixano.datasets.utils.integrity import validate_batch

        dataset = _make_dataset(tmp_path / "ds")
        ghost_box = BBox(
            id="boxg",
            record_id="recg",
            entity_id="entg",
            coords=[0.1, 0.1, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        )

        # Ledger says the parents exist: no error despite an empty DB.
        validate_batch(
            "bboxes",
            [ghost_box],
            {},
            dataset,
            raise_or_warn="raise",
            fk_lookup=lambda table, values: {value: True for value in values},
        )

        # Ledger says they don't: same call fails.
        with pytest.raises(DatasetIntegrityError):
            validate_batch(
                "bboxes",
                [ghost_box],
                {},
                dataset,
                raise_or_warn="raise",
                fk_lookup=lambda table, values: {value: False for value in values},
            )


class TestFeaturesValuesBridges:
    def test_add_constraint_on_records_table(self, tmp_path: Path):
        dataset = _make_dataset(tmp_path / "ds")
        dataset.add_constraint("records", "status", ["new", "validated"])

        constraints = dataset.features_values.records["records"]
        assert constraints[0].name == "status"
        reloaded = type(dataset.features_values).from_json(tmp_path / "ds" / "features_values.json")
        assert reloaded.records["records"][0].values == ["new", "validated"]
