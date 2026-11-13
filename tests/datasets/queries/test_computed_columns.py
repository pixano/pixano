# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Records ordered and filtered through their statistics, joined with DuckDB on a real dataset."""

import random
from datetime import timedelta
from pathlib import Path

import pyarrow as pa
import pytest
from pydantic import create_model

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.queries.computed_columns import (
    ComputedFilter,
    InvalidRecordFilter,
    RecordOrder,
    computed_values,
    matching_record_ids,
    ordered_record_ids,
    quote_identifier,
    record_neighbors,
)
from pixano.schemas import Image, Record
from pixano.statistics.definitions import StatisticLevel


SplitRecord = create_model("SplitRecord", __base__=Record, rank=(int, 0))
COLUMNS = {"bbox_count": "int", "bbox_area_mean_px": "float"}

#: r1 to r6, their rank, and their statistics: r4's are none, r5 has no row, r6 has the most boxes.
RECORDS = {"r1": 3, "r2": 1, "r3": 2, "r4": 5, "r5": 4, "r6": 6}
VALUES = {
    "r1": {"bbox_count": 3, "bbox_area_mean_px": 10.5},
    "r2": {"bbox_count": 1, "bbox_area_mean_px": 4.0},
    "r3": {"bbox_count": 3, "bbox_area_mean_px": None},
    "r4": {"bbox_count": None, "bbox_area_mean_px": None},
    "r6": {"bbox_count": 7, "bbox_area_mean_px": 2.0},
}


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    return tmp_path / "ds"


def _dataset(folder: Path, with_statistics: bool = True) -> Dataset:
    dataset = Dataset.create(folder, DatasetInfo(id="ds", name="ds", record=SplitRecord, views={"image": Image}))
    dataset.add_records({"records": [SplitRecord(id=record, rank=rank) for record, rank in RECORDS.items()]})
    if with_statistics:
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, COLUMNS)
        dataset.write_statistic_values(
            StatisticLevel.RECORD,
            [{"id": record, "record_id": record, **values} for record, values in VALUES.items()],
            COLUMNS,
        )
    return dataset


def _by(column: str, descending: bool = False) -> RecordOrder:
    return RecordOrder(column=column, descending=descending, on_computed=column in COLUMNS)


class TestOrder:
    def test_on_a_statistic_those_without_come_last(self, folder: Path) -> None:
        # r1 and r3 are equal: their identifiers order them.
        assert ordered_record_ids(_dataset(folder), None, None, _by("bbox_count")) == (
            ["r2", "r1", "r3", "r6", "r4", "r5"],
            6,
        )

    def test_descending_those_without_still_come_last(self, folder: Path) -> None:
        assert ordered_record_ids(_dataset(folder), None, None, _by("bbox_count", descending=True)) == (
            ["r6", "r1", "r3", "r2", "r4", "r5"],
            6,
        )

    def test_on_a_column_of_the_records(self, folder: Path) -> None:
        assert ordered_record_ids(_dataset(folder), None, None, _by("rank", descending=True))[0] == [
            "r6",
            "r4",
            "r5",
            "r1",
            "r3",
            "r2",
        ]

    def test_pages_follow_one_another_without_overlap(self, folder: Path) -> None:
        dataset = _dataset(folder)
        order = _by("bbox_count")

        pages = [ordered_record_ids(dataset, None, None, order, limit=4, offset=offset) for offset in (0, 4, 8)]

        assert pages == [(["r2", "r1", "r3", "r6"], 6), (["r4", "r5"], 6), ([], 6)]


class TestFilter:
    def test_on_a_statistic(self, folder: Path) -> None:
        condition = ComputedFilter(sql='c."bbox_count" >= 3', columns=("bbox_count",))

        assert ordered_record_ids(_dataset(folder), None, condition, _by("id")) == (["r1", "r3", "r6"], 3)

    def test_on_a_statistic_and_on_the_records(self, folder: Path) -> None:
        condition = ComputedFilter(sql='c."bbox_count" >= 3', columns=("bbox_count",))

        assert ordered_record_ids(
            _dataset(folder), "rank >= 2", condition, _by("bbox_area_mean_px", descending=True)
        ) == (
            ["r1", "r6", "r3"],
            3,
        )

    def test_a_record_without_the_value_matches_no_comparison(self, folder: Path) -> None:
        condition = ComputedFilter(sql='c."bbox_count" != 3', columns=("bbox_count",))

        assert ordered_record_ids(_dataset(folder), None, condition, _by("id"))[0] == ["r2", "r6"]


class TestBeforeAnyComputation:
    def test_every_record_is_without_statistics(self, folder: Path) -> None:
        assert ordered_record_ids(_dataset(folder, with_statistics=False), None, None, _by("bbox_count")) == (
            ["r1", "r2", "r3", "r4", "r5", "r6"],
            6,
        )

    def test_no_record_matches_a_condition_on_them(self, folder: Path) -> None:
        condition = ComputedFilter(sql='c."bbox_count" >= 0', columns=("bbox_count",))

        assert ordered_record_ids(_dataset(folder, with_statistics=False), None, condition, _by("id")) == ([], 0)

    def test_nor_on_a_column_not_computed_yet(self, folder: Path) -> None:
        condition = ComputedFilter(sql='c."mask_count" >= 0', columns=("mask_count",))

        assert ordered_record_ids(_dataset(folder), None, condition, _by("id")) == ([], 0)


class TestValues:
    def test_of_the_records_asked(self, folder: Path) -> None:
        assert computed_values(_dataset(folder), ["r1", "r4", "r5"], ["bbox_count", "bbox_area_mean_px"]) == {
            "r1": {"bbox_count": 3, "bbox_area_mean_px": 10.5},
            "r4": {"bbox_count": None, "bbox_area_mean_px": None},
        }

    def test_of_the_columns_there(self, folder: Path) -> None:
        assert computed_values(_dataset(folder), ["r2"], ["bbox_count", "mask_count"]) == {"r2": {"bbox_count": 1}}

    @pytest.mark.parametrize("with_statistics", [True, False])
    def test_none_to_read(self, folder: Path, with_statistics: bool) -> None:
        dataset = _dataset(folder, with_statistics)

        assert computed_values(dataset, [], ["bbox_count"]) == {}
        assert computed_values(dataset, ["r1"], []) == {}
        if not with_statistics:
            assert computed_values(dataset, ["r1"], ["bbox_count"]) == {}


class TestNeighbors:
    @pytest.mark.parametrize(
        "record,expected",
        [
            ("r2", {"prev": None, "next": "r1", "position": 1, "total": 6}),
            ("r1", {"prev": "r2", "next": "r3", "position": 2, "total": 6}),
            ("r5", {"prev": "r4", "next": None, "position": 6, "total": 6}),
        ],
    )
    def test_in_an_order_on_a_statistic(self, folder: Path, record: str, expected: dict) -> None:
        assert record_neighbors(_dataset(folder), None, None, _by("bbox_count"), record) == expected

    @pytest.mark.parametrize(
        "record,expected",
        [
            ("r6", {"prev": None, "next": "r1", "position": 1, "total": 6}),
            ("r3", {"prev": "r1", "next": "r2", "position": 3, "total": 6}),
            ("r4", {"prev": "r2", "next": "r5", "position": 5, "total": 6}),
            ("r5", {"prev": "r4", "next": None, "position": 6, "total": 6}),
        ],
    )
    def test_descending_ties_by_identifier_and_those_without_last(
        self, folder: Path, record: str, expected: dict
    ) -> None:
        assert record_neighbors(_dataset(folder), None, None, _by("bbox_count", descending=True), record) == expected

    def test_of_a_record_the_conditions_leave_out(self, folder: Path) -> None:
        condition = ComputedFilter(sql='c."bbox_count" >= 3', columns=("bbox_count",))

        assert record_neighbors(_dataset(folder), None, condition, _by("id"), "r2") == {
            "prev": None,
            "next": None,
            "position": None,
            "total": 3,
        }

    def test_in_an_order_on_a_column_of_the_records(self, folder: Path) -> None:
        assert record_neighbors(_dataset(folder), "rank > 1", None, _by("rank"), "r1") == {
            "prev": "r3",
            "next": "r5",
            "position": 2,
            "total": 5,
        }


class TestMatching:
    def test_the_records_both_conditions_keep(self, folder: Path) -> None:
        condition = ComputedFilter(sql='c."bbox_count" >= 3', columns=("bbox_count",))

        assert sorted(matching_record_ids(_dataset(folder), "rank < 6", condition)) == ["r1", "r3"]


class TestRobustness:
    def test_a_condition_on_the_records_lance_refuses(self, folder: Path) -> None:
        with pytest.raises(InvalidRecordFilter):
            ordered_record_ids(_dataset(folder), "rank = = 1", None, _by("bbox_count"))

    def test_a_record_with_two_rows_of_statistics_shows_once(self, folder: Path) -> None:
        """Two merges at once on S3, where no lock holds them apart, could store two."""
        dataset = _dataset(folder)
        table = dataset.open_table("record_statistics")
        table.add(
            pa.table(
                {"id": ["r2"], "record_id": ["r2"], "bbox_count": [9], "bbox_area_mean_px": [1.0]}, schema=table.schema
            )
        )

        ids, total = ordered_record_ids(dataset, None, None, _by("bbox_count"))

        assert (ids.count("r2"), total) == (1, 6)

    def test_statistics_compacted_by_another_process_since_the_dataset_was_opened(self, folder: Path) -> None:
        """Another process writes and compacts the table while the application holds the dataset open."""
        dataset = _dataset(folder)
        assert ordered_record_ids(dataset, None, None, _by("bbox_count"))[0][0] == "r2"
        writer = Dataset(folder)
        writer.write_statistic_values(
            StatisticLevel.RECORD, [{"record_id": "r2", "bbox_count": 9}], {"bbox_count": "int"}
        )
        writer.open_table("record_statistics").optimize(cleanup_older_than=timedelta(0))

        assert ordered_record_ids(dataset, None, None, _by("bbox_count"))[0][:2] == ["r1", "r3"]
        assert computed_values(dataset, ["r2"], ["bbox_count"]) == {"r2": {"bbox_count": 9}}

    def test_a_statistics_table_that_cannot_be_read_shows_no_value(self, folder: Path, monkeypatch) -> None:
        dataset = _dataset(folder)

        def broken(name: str) -> None:
            raise OSError("a file of the table is gone")

        monkeypatch.setattr(dataset, "open_latest_table", broken)

        assert computed_values(dataset, ["r1"], ["bbox_count"]) == {}

    def test_a_column_name_holding_a_quote_stays_a_name(self) -> None:
        assert quote_identifier('odd"name') == '"odd""name"'


def _random_dataset(folder: Path, seed: int) -> Dataset:
    """Forty records, ranked at random among few ranks; their statistic among few values, or none."""
    generator = random.Random(seed)
    dataset = Dataset.create(folder, DatasetInfo(id="ds", name="ds", record=SplitRecord, views={"image": Image}))
    records = [SplitRecord(id=f"r{index:02d}", rank=generator.randint(0, 3)) for index in range(40)]
    dataset.add_records({"records": records})
    dataset.ensure_statistic_columns(StatisticLevel.RECORD, {"bbox_count": "int"})
    rows = [
        {"record_id": record.id, "bbox_count": generator.choice([None, 0, 1, 1, 2, 5])}
        for record in records
        if generator.random() > 0.1
    ]
    dataset.write_statistic_values(StatisticLevel.RECORD, rows, {"bbox_count": "int"})
    return dataset


@pytest.mark.parametrize("seed", [1, 2])
@pytest.mark.parametrize("column", ["bbox_count", "rank", "id"])
@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("filtered", [False, True])
def test_neighbors_agree_with_the_order_of_the_pages(
    tmp_path: Path, seed: int, column: str, descending: bool, filtered: bool
) -> None:
    """Counted rather than sorted, a record's neighbors are its neighbors in the pages' order."""
    dataset = _random_dataset(tmp_path / "ds", seed)
    order = RecordOrder(column=column, descending=descending, on_computed=column == "bbox_count")
    condition = ComputedFilter(sql='c."bbox_count" >= 1', columns=("bbox_count",)) if filtered else None
    ordered, total = ordered_record_ids(dataset, None, condition, order)

    for position, record in enumerate(ordered):
        assert record_neighbors(dataset, None, condition, order, record) == {
            "prev": ordered[position - 1] if position > 0 else None,
            "next": ordered[position + 1] if position < len(ordered) - 1 else None,
            "position": position + 1,
            "total": total,
        }


class TestUnreadableStatistics:
    def test_a_read_that_fails_once_is_tried_again(self, folder: Path, monkeypatch) -> None:
        """A compaction may take the files of the version first read away."""
        dataset = _dataset(folder)
        opened = dataset.open_latest_table
        calls = []

        def compacted_once(name: str):
            calls.append(name)
            if len(calls) == 1:
                raise OSError("a file of the version read is gone")
            return opened(name)

        monkeypatch.setattr(dataset, "open_latest_table", compacted_once)

        assert computed_values(dataset, ["r1"], ["bbox_count"]) == {"r1": {"bbox_count": 3}}

    def test_the_join_finds_no_value_where_the_table_cannot_be_read(self, folder: Path, monkeypatch) -> None:
        dataset = _dataset(folder)

        def broken(name: str) -> None:
            raise OSError("the table is gone")

        monkeypatch.setattr(dataset, "open_latest_table", broken)
        condition = ComputedFilter(sql='c."bbox_count" >= 0', columns=("bbox_count",))

        assert ordered_record_ids(dataset, None, condition, _by("id")) == ([], 0)
        assert ordered_record_ids(dataset, None, None, _by("bbox_count"))[0] == ["r1", "r2", "r3", "r4", "r5", "r6"]
