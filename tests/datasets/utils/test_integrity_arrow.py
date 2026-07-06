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
from pixano.datasets.utils.integrity import validate_arrow_batch
from pixano.schemas import BBox, Entity, Image, Record


@pytest.fixture()
def dataset(tmp_path: Path) -> Dataset:
    info = DatasetInfo(name="arrow_ds", record=Record, entity=Entity, bbox=BBox, views={"image": Image})
    ds = Dataset.create(tmp_path / "ds", info)
    ds.merge_records({"records": Record(id="rec1")}, check_integrity="none")
    return ds


def _entities(ids: list[str], record_ids: list[str]) -> pa.RecordBatch:
    return pa.record_batch({"id": pa.array(ids), "record_id": pa.array(record_ids)})


class TestValidateArrowBatch:
    def test_clean_batch_passes(self, dataset: Dataset):
        validate_arrow_batch("entities", _entities(["e1", "e2"], ["rec1", "rec1"]), {}, dataset)

    def test_dangling_fk_raises_like_the_row_path(self, dataset: Dataset):
        with pytest.raises(DatasetIntegrityError, match="ghost"):
            validate_arrow_batch("entities", _entities(["e1"], ["ghost"]), {}, dataset)

    def test_empty_id_raises(self, dataset: Dataset):
        with pytest.raises(DatasetIntegrityError, match="[Mm]issing id"):
            validate_arrow_batch("entities", _entities([""], ["rec1"]), {}, dataset)

    def test_duplicate_ids_in_batch_raise(self, dataset: Dataset):
        with pytest.raises(DatasetIntegrityError, match="e1"):
            validate_arrow_batch("entities", _entities(["e1", "e1"], ["rec1", "rec1"]), {}, dataset)

    def test_known_ids_flag_cross_flush_duplicates(self, dataset: Dataset):
        with pytest.raises(DatasetIntegrityError, match="e1"):
            validate_arrow_batch(
                "entities", _entities(["e1"], ["rec1"]), {"entities": {"e1"}}, dataset
            )

    def test_empty_fk_sentinel_is_skipped(self, dataset: Dataset):
        validate_arrow_batch("entities", _entities(["e1"], [""]), {}, dataset)

    def test_pending_and_known_ids_resolve_fks_without_db(self, dataset: Dataset):
        batch = _entities(["e1", "e2"], ["pending_rec", "known_rec"])
        validate_arrow_batch(
            "entities",
            batch,
            {"records": {"known_rec"}},
            dataset,
            pending_ids={"records": {"pending_rec"}},
        )

    def test_fk_lookup_override(self, dataset: Dataset):
        calls: list[tuple[str, set[str]]] = []

        def ledger_lookup(target: str, values: set[str]) -> dict[str, bool]:
            calls.append((target, values))
            return {value: value == "ledger_rec" for value in values}

        validate_arrow_batch(
            "entities", _entities(["e1"], ["ledger_rec"]), {}, dataset, fk_lookup=ledger_lookup
        )
        assert calls == [("records", {"ledger_rec"})]

    def test_warn_mode_does_not_raise(self, dataset: Dataset):
        validate_arrow_batch("entities", _entities(["e1"], ["ghost"]), {}, dataset, raise_or_warn="warn")


class TestMergeRecordsArrowIntegration:
    def test_engine_parity_same_error_code(self, dataset: Dataset):
        # Direct merge_records call and the row path produce the same FK_ID failure.
        with pytest.raises(DatasetIntegrityError, match="ghost"):
            dataset.merge_records({"entities": _entities(["e1"], ["ghost"])}, check_integrity="raise")
        with pytest.raises(DatasetIntegrityError, match="ghost"):
            dataset.merge_records({"entities": Entity(id="e1", record_id="ghost")}, check_integrity="raise")

    def test_arrow_fk_resolved_by_row_sibling_in_same_call(self, dataset: Dataset):
        # Full-schema batch: lance merge_insert requires all columns.
        entities_schema = dataset.open_table("entities").schema
        full_batch = pa.Table.from_pylist([Entity(id="e9", record_id="rec2").model_dump()], schema=entities_schema)
        counts = dataset.merge_records(
            {
                "records": Record(id="rec2"),
                "entities": full_batch,
            },
            check_integrity="raise",
        )
        assert counts == {"records": 1, "entities": 1}
