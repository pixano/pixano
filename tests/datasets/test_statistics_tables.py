# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A dataset's statistics: a table per level, a column per statistic, and what the dataset computed."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from lancedb.merge import LanceMergeInsertBuilder

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.io import ImportSpec, SpecValidationError, resolve_dataset_info
from pixano.datasets.io.reader import RecordBundleReader
from pixano.datasets.io.spec import SchemaSpec
from pixano.schemas import BBox, Entity, EntityStatistics, Image, Record, RecordStatistics
from pixano.statistics.computed import ComputedStatistic
from pixano.statistics.definitions import StatisticChoices, StatisticLevel, StatisticMeasure, define_statistic


RECORD_TABLE = "record_statistics"
ENTITY_TABLE = "entity_statistics"


def _dataset(tmp_path: Path) -> Dataset:
    target = tmp_path / "ds"
    dataset = Dataset.create(
        target, DatasetInfo(id="ds", name="ds", record=Record, entity=Entity, bbox=BBox, views={"image": Image})
    )
    dataset.add_records({"records": [Record(id="r1"), Record(id="r2")]})
    return dataset


def _info_json(dataset: Dataset) -> dict:
    return json.loads((dataset.path / "info.json").read_text(encoding="utf-8"))


BOTH_COUNTS = {"bbox_count": "int", "mask_count": "int"}


def _write(dataset: Dataset, values: dict[str, dict[str, int]], columns: dict[str, str] = BOTH_COUNTS) -> None:
    dataset.write_statistic_values(
        StatisticLevel.RECORD, [{"record_id": record, **counts} for record, counts in values.items()], columns
    )


def _counts(dataset: Dataset) -> list[tuple[str, int | None, int | None]]:
    rows = sorted(dataset.open_table(RECORD_TABLE).to_arrow().to_pylist(), key=lambda row: row["id"])
    return [(row["id"], row["bbox_count"], row["mask_count"]) for row in rows]


def _rewritten_then_indexed(tmp_path: Path) -> Dataset:
    """Two counts per record, r1's computed again, then `id` indexed as an import indexes it."""
    dataset = _dataset(tmp_path)
    dataset.ensure_statistic_columns(StatisticLevel.RECORD, BOTH_COUNTS)
    _write(dataset, {"r1": {"bbox_count": 1, "mask_count": 1}, "r2": {"bbox_count": 1, "mask_count": 1}})
    _write(dataset, {"r1": {"bbox_count": 2, "mask_count": 2}})
    dataset.create_scalar_indexes(tables=[RECORD_TABLE])
    return dataset


def _computed(element: str = "bbox", job_id: str = "job-1") -> ComputedStatistic:
    choices = StatisticChoices(level=StatisticLevel.RECORD, element=element, measure=StatisticMeasure.COUNT)
    return ComputedStatistic(
        definition=define_statistic(choices), job_id=job_id, computed_at=datetime(2026, 11, 4, tzinfo=timezone.utc)
    )


class TestEnsureStatisticColumns:
    def test_creates_the_table_of_the_level_and_declares_it(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        assert dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"}) == RECORD_TABLE

        assert dataset.info.record_statistics is RecordStatistics
        assert _info_json(dataset)["record_statistics"] == {"base": "RecordStatistics", "fields": {}}
        assert Dataset(dataset.path).info.tables[RECORD_TABLE] is RecordStatistics

    def test_a_column_per_statistic_typed_as_its_values_and_nullable(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int", "bbox_area_mean_px": "float"})

        schema = dataset.open_table(RECORD_TABLE).schema
        assert (schema.field("bbox_count").type, schema.field("bbox_count").nullable) == (pa.int64(), True)
        assert (schema.field("bbox_area_mean_px").type, schema.field("bbox_area_mean_px").nullable) == (
            pa.float64(),
            True,
        )

    def test_a_column_added_later_is_null_for_the_rows_already_there(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})
        dataset.open_table(RECORD_TABLE).add(
            pa.table({"id": ["r1"], "record_id": ["r1"], "bbox_count": pa.array([3], pa.int64())})
        )

        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"mask_count": "int"})

        assert dataset.open_table(RECORD_TABLE).to_arrow().to_pylist() == [
            {"id": "r1", "record_id": "r1", "bbox_count": 3, "mask_count": None}
        ]

    def test_columns_already_there_write_nothing(self, tmp_path: Path) -> None:
        """To be called by every chunk of a job: a rewrite of info.json would make the API reopen the dataset."""
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})
        held = Dataset(dataset.path)

        Dataset(dataset.path).ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})

        assert not held.is_stale()

    def test_a_column_of_another_type_is_refused(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})

        with pytest.raises(ValueError):
            dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "float"})

    def test_a_column_every_row_carries_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            _dataset(tmp_path).ensure_statistic_columns(StatisticLevel.ENTITY, {"entity_id": "int"})

    @pytest.mark.parametrize("column", ["record.count", "_rowid", "", "Count", "x" * 64])
    def test_a_name_no_statistic_has_is_refused(self, tmp_path: Path, column: str) -> None:
        """The columns are to come from a job's parameters, which anybody can send."""
        with pytest.raises(ValueError, match="no statistic's column name"):
            _dataset(tmp_path).ensure_statistic_columns(StatisticLevel.RECORD, {column: "int"})

    def test_values_of_no_statistics_type_are_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="int or float"):
            _dataset(tmp_path).ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "str"})

    def test_the_objects_table_names_its_object(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        assert dataset.ensure_statistic_columns(StatisticLevel.ENTITY, {"bbox_count": "int"}) == ENTITY_TABLE

        assert dataset.info.entity_statistics is EntityStatistics
        assert "entity_id" in dataset.open_table(ENTITY_TABLE).schema.names

    def test_the_rows_of_a_deleted_record_go_with_it(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})
        dataset.open_table(RECORD_TABLE).add(
            pa.table({"id": ["r1", "r2"], "record_id": ["r1", "r2"], "bbox_count": pa.array([1, 2], pa.int64())})
        )

        dataset.delete_records(["r1"])

        assert [row["record_id"] for row in dataset.open_table(RECORD_TABLE).to_arrow().to_pylist()] == ["r2"]

    def test_the_rows_of_the_objects_of_a_deleted_record_go_with_it(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.add_data(
            "entities", [Entity(id="e1", record_id="r1"), Entity(id="e2", record_id="r2")], raise_or_warn="none"
        )
        dataset.ensure_statistic_columns(StatisticLevel.ENTITY, {"bbox_count": "int"})
        dataset.write_statistic_values(
            StatisticLevel.ENTITY,
            [
                {"record_id": "r1", "entity_id": "e1", "bbox_count": 1},
                {"record_id": "r2", "entity_id": "e2", "bbox_count": 2},
            ],
            {"bbox_count": "int"},
        )

        dataset.delete_records(["r1"])

        assert [row["entity_id"] for row in dataset.open_table(ENTITY_TABLE).to_arrow().to_pylist()] == ["e2"]

    def test_a_rows_identifier_is_its_records(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})

        dataset.write_statistic_values(
            StatisticLevel.RECORD, [{"id": "an-annotation", "record_id": "r1", "bbox_count": 1}], {"bbox_count": "int"}
        )

        assert [row["id"] for row in dataset.open_table(RECORD_TABLE).to_arrow().to_pylist()] == ["r1"]

    def test_two_rows_of_one_record_are_refused(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})

        with pytest.raises(ValueError, match="two rows"):
            dataset.write_statistic_values(
                StatisticLevel.RECORD,
                [{"record_id": "r1", "bbox_count": 1}, {"record_id": "r1", "bbox_count": 2}],
                {"bbox_count": "int"},
            )

    def test_a_column_not_there_is_refused(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})

        with pytest.raises(ValueError, match="ensure them first"):
            dataset.write_statistic_values(
                StatisticLevel.RECORD, [{"record_id": "r1", "mask_count": 1}], {"mask_count": "int"}
            )

    def test_the_rows_of_a_record_deleted_since_it_was_measured_are_not_written(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})
        dataset.delete_records(["r2"])

        dataset.write_statistic_values(
            StatisticLevel.RECORD,
            [{"record_id": "r1", "bbox_count": 1}, {"record_id": "r2", "bbox_count": 2}],
            {"bbox_count": "int"},
        )

        assert [row["id"] for row in dataset.open_table(RECORD_TABLE).to_arrow().to_pylist()] == ["r1"]

    def test_a_jobs_own_columns_into_a_table_an_import_indexed(self, tmp_path: Path) -> None:
        """An import indexes `id` on every table: a later job writes its columns only, beside others."""
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})
        dataset.write_statistic_values(
            StatisticLevel.RECORD, [{"record_id": "r1", "bbox_count": 1}], {"bbox_count": "int"}
        )
        dataset.create_scalar_indexes(tables=[RECORD_TABLE])
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"mask_count": "int"})

        dataset.write_statistic_values(
            StatisticLevel.RECORD,
            [{"record_id": "r1", "mask_count": 7}, {"record_id": "r2", "mask_count": 8}],
            {"mask_count": "int"},
        )

        rows = sorted(dataset.open_table(RECORD_TABLE).to_arrow().to_pylist(), key=lambda row: row["id"])
        assert [(row["id"], row["bbox_count"], row["mask_count"]) for row in rows] == [("r1", 1, 7), ("r2", None, 8)]


class TestRecordComputedStatistics:
    def test_what_a_job_computed_is_kept_in_info_json(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        computed = _computed()

        dataset.record_computed_statistics([computed])

        reopened = Dataset(dataset.path)
        assert reopened.info.statistics == [computed]
        assert _info_json(dataset)["statistics"][0]["computed_at"] == "2026-11-04T00:00:00Z"

    def test_a_statistic_computed_again_replaces_the_previous_and_keeps_the_others(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.record_computed_statistics([_computed("bbox", "job-1"), _computed("entity", "job-1")])

        dataset.record_computed_statistics([_computed("bbox", "job-2")])

        assert [
            (statistic.definition.name, statistic.job_id) for statistic in Dataset(dataset.path).info.statistics
        ] == [
            ("entity_count", "job-1"),
            ("bbox_count", "job-2"),
        ]

    def test_a_statistic_given_twice_is_kept_once_the_last(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        dataset.record_computed_statistics([_computed("bbox", "job-1"), _computed("bbox", "job-2")])

        assert [(statistic.definition.name, statistic.job_id) for statistic in dataset.info.statistics] == [
            ("bbox_count", "job-2")
        ]

    def test_written_whole_with_the_rest_of_the_info_and_read_back(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.record_computed_statistics([_computed()])
        info_file = tmp_path / "info.json"

        dataset.info.to_json(info_file)

        assert DatasetInfo.from_json(info_file).statistics == dataset.info.statistics

    def test_one_that_no_longer_reads_does_not_keep_the_dataset_from_opening(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Composed under a rule changed since: the dataset opens, without it."""
        dataset = _dataset(tmp_path)
        dataset.record_computed_statistics([_computed()])
        info = _info_json(dataset)
        outdated = json.loads(json.dumps(info["statistics"][0]))
        outdated["definition"]["choices"]["origin"] = "an origin no longer known"
        info["statistics"].append(outdated)
        (dataset.path / "info.json").write_text(json.dumps(info), encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="pixano.datasets.dataset_info"):
            reopened = Dataset(dataset.path)

        assert [statistic.definition.name for statistic in reopened.info.statistics] == ["bbox_count"]
        assert any("no longer reads" in record.getMessage() for record in caplog.records)

        # Another statistic recorded since keeps the one this build no longer reads, as written.
        reopened.record_computed_statistics([_computed("entity")])
        assert [entry["definition"]["choices"].get("origin") for entry in _info_json(dataset)["statistics"]] == [
            None,
            "an origin no longer known",
            None,
        ]


class TestStatisticsStayWithTheDataset:
    """Statistics are computed from a dataset, and computed again on another: no export carries them."""

    def test_an_export_declares_no_statistics_table(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})

        spec = SchemaSpec.from_dataset_info(Dataset(dataset.path).info)

        assert spec.annotations == ["bbox"]

    def test_an_export_reads_no_statistics_row(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})
        dataset.open_table(RECORD_TABLE).add(
            pa.table({"id": ["r1"], "record_id": ["r1"], "bbox_count": pa.array([1], pa.int64())})
        )

        bundles = list(RecordBundleReader().iter_bundles(Dataset(dataset.path)))

        assert all(RECORD_TABLE not in bundle.components for bundle in bundles)


class TestWriteStatisticValues:
    def test_writes_the_columns_given_and_keeps_the_others(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int", "mask_count": "int"})
        dataset.write_statistic_values(
            StatisticLevel.RECORD,
            [{"id": "r1", "record_id": "r1", "bbox_count": 2, "mask_count": 5}],
            {"bbox_count": "int", "mask_count": "int"},
        )

        dataset.write_statistic_values(
            StatisticLevel.RECORD,
            [{"id": "r1", "record_id": "r1", "bbox_count": 3}, {"id": "r2", "record_id": "r2", "bbox_count": 0}],
            {"bbox_count": "int"},
        )

        rows = sorted(dataset.open_table(RECORD_TABLE).to_arrow().to_pylist(), key=lambda row: row["id"])
        assert rows == [
            {"id": "r1", "record_id": "r1", "bbox_count": 3, "mask_count": 5},
            {"id": "r2", "record_id": "r2", "bbox_count": 0, "mask_count": None},
        ]

    def test_an_objects_row_names_its_object_and_takes_no_value(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.add_data("entities", [Entity(id="e1", record_id="r1")], raise_or_warn="none")
        dataset.ensure_statistic_columns(StatisticLevel.ENTITY, {"bbox_area_mean_px": "float"})

        dataset.write_statistic_values(
            StatisticLevel.ENTITY,
            [{"id": "e1", "record_id": "r1", "entity_id": "e1", "bbox_area_mean_px": None}],
            {"bbox_area_mean_px": "float"},
        )

        assert dataset.open_table(ENTITY_TABLE).to_arrow().to_pylist() == [
            {"id": "e1", "record_id": "r1", "entity_id": "e1", "bbox_area_mean_px": None}
        ]

    def test_an_objects_other_statistics_are_kept_and_a_new_objects_are_none(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.add_data(
            "entities", [Entity(id="e1", record_id="r1"), Entity(id="e2", record_id="r1")], raise_or_warn="none"
        )
        dataset.ensure_statistic_columns(StatisticLevel.ENTITY, BOTH_COUNTS)
        dataset.write_statistic_values(
            StatisticLevel.ENTITY,
            [{"record_id": "r1", "entity_id": "e1", "bbox_count": 1, "mask_count": 2}],
            BOTH_COUNTS,
        )

        dataset.write_statistic_values(
            StatisticLevel.ENTITY,
            [
                {"record_id": "r1", "entity_id": "e1", "mask_count": 3},
                {"record_id": "r1", "entity_id": "e2", "mask_count": 4},
            ],
            {"mask_count": "int"},
        )

        rows = sorted(dataset.open_table(ENTITY_TABLE).to_arrow().to_pylist(), key=lambda row: row["id"])
        assert rows == [
            {"id": "e1", "record_id": "r1", "entity_id": "e1", "bbox_count": 1, "mask_count": 3},
            {"id": "e2", "record_id": "r1", "entity_id": "e2", "bbox_count": None, "mask_count": 4},
        ]

    def test_a_column_holding_values_of_another_type_is_refused(self, tmp_path: Path) -> None:
        """A count written into a column of areas would be kept as 1.0, silently."""
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_area_mean_px": "float"})

        with pytest.raises(ValueError, match="holds double, not int"):
            dataset.write_statistic_values(
                StatisticLevel.RECORD, [{"record_id": "r1", "bbox_area_mean_px": 1}], {"bbox_area_mean_px": "int"}
            )

    def test_lance_is_given_every_column_of_the_table_in_its_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Whatever Lance makes of some columns, or of columns in another order: it is never given any."""
        dataset = _dataset(tmp_path)
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, BOTH_COUNTS)
        given: list[pa.Schema] = []
        execute = LanceMergeInsertBuilder.execute

        def recording(builder: LanceMergeInsertBuilder, new_data: pa.Table, *args: Any, **kwargs: Any) -> Any:
            given.append(new_data.schema)
            return execute(builder, new_data, *args, **kwargs)

        monkeypatch.setattr(LanceMergeInsertBuilder, "execute", recording)
        _write(dataset, {"r1": {"mask_count": 1}}, {"mask_count": "int"})
        _write(dataset, {"r2": {"mask_count": 2, "bbox_count": 3}}, {"mask_count": "int", "bbox_count": "int"})

        assert given == [dataset.open_table(RECORD_TABLE).schema] * 2

    def test_columns_in_another_order_once_a_statistic_computed_again_is_indexed(self, tmp_path: Path) -> None:
        """Lance merges columns in another order by rewriting them in place: on a table whose `id` is
        indexed, as an import indexes it, once a statistic computed again replaced rows, that left the
        next write failing ("Ambiguous merge insert")."""
        dataset = _rewritten_then_indexed(tmp_path)

        _write(dataset, {"r2": {"mask_count": 3, "bbox_count": 3}}, {"mask_count": "int", "bbox_count": "int"})
        _write(dataset, {"r1": {"bbox_count": 4, "mask_count": 5}, "r2": {"bbox_count": 6, "mask_count": 7}})

        assert _counts(dataset) == [("r1", 4, 5), ("r2", 6, 7)]

    def test_a_jobs_own_columns_once_a_statistic_computed_again_is_indexed(self, tmp_path: Path) -> None:
        """A job writes its own columns, beside the others: the case above, for its usual write."""
        dataset = _rewritten_then_indexed(tmp_path)

        _write(dataset, {"r2": {"mask_count": 3}}, {"mask_count": "int"})
        assert _counts(dataset) == [("r1", 2, 2), ("r2", 1, 3)]
        _write(dataset, {"r1": {"bbox_count": 5, "mask_count": 6}, "r2": {"bbox_count": 7, "mask_count": 8}})

        assert _counts(dataset) == [("r1", 5, 6), ("r2", 7, 8)]

    def test_the_info_an_export_carries_holds_no_statistics(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.record_computed_statistics([_computed()])

        assert "statistics" not in dataset.info.json_info_dump()

    def test_an_import_takes_no_statistics_table(self) -> None:
        manifest = {
            "record": {"base": "Record", "fields": {}},
            "record_statistics": {"base": "RecordStatistics", "fields": {}},
        }
        spec = ImportSpec.model_validate({"dataset": {"workspace": "image"}, "schema_manifest": manifest})

        with pytest.raises(SpecValidationError, match="no statistics table"):
            resolve_dataset_info(spec)

    def test_an_entry_of_an_import_that_is_no_schema_is_refused_as_such(self) -> None:
        manifest = {"record": {"base": "Record", "fields": {}}, "statistics": [{"job_id": "job-1"}]}
        spec = ImportSpec.model_validate({"dataset": {"workspace": "image"}, "schema_manifest": manifest})

        with pytest.raises(SpecValidationError, match="Invalid schema_manifest"):
            resolve_dataset_info(spec)
