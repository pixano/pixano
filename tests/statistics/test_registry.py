# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The library's registry of statistics: composed once, kept for every dataset."""

import hashlib
import logging
import threading
from pathlib import Path

import lancedb
import pyarrow as pa
import pytest

from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import Record
from pixano.statistics import definitions as definitions_module
from pixano.statistics.definitions import (
    AttributeFilter,
    StatisticAggregation,
    StatisticChoices,
    StatisticLevel,
    StatisticMeasure,
    define_statistic,
)
from pixano.statistics.registry import _SCHEMA, DEFINITIONS_TABLE, LIBRARY_STORE_DIR, StatisticRegistry, _row_of


def _count(level: StatisticLevel = StatisticLevel.RECORD, **changes) -> StatisticChoices:
    return StatisticChoices(level=level, element="bbox", measure=StatisticMeasure.COUNT, **changes)


def _store(library: Path) -> lancedb.table.Table:
    return lancedb.connect(library / LIBRARY_STORE_DIR).open_table(DEFINITIONS_TABLE)


class TestRegistry:
    def test_an_empty_library_has_none_and_creates_nothing(self, tmp_path: Path) -> None:
        assert StatisticRegistry(tmp_path).definitions() == []
        assert not (tmp_path / LIBRARY_STORE_DIR).exists()

    def test_a_statistic_added_is_kept_for_the_library(self, tmp_path: Path) -> None:
        definition = define_statistic(_count(), label="Boxes")

        stored, added = StatisticRegistry(tmp_path).add(definition)

        assert added
        assert stored == definition
        assert StatisticRegistry(tmp_path).definitions() == [definition]
        assert StatisticRegistry(tmp_path).get(StatisticLevel.RECORD, "bbox_count") == definition

    def test_the_store_is_no_dataset_of_the_library(self, tmp_path: Path) -> None:
        Dataset.create(tmp_path / "ds", DatasetInfo(id="ds", name="ds", record=Record))
        StatisticRegistry(tmp_path).add(define_statistic(_count()))

        assert [info.id for info in DatasetInfo.load_directory(tmp_path)] == ["ds"]

    def test_composing_it_again_gives_the_one_there(self, tmp_path: Path) -> None:
        first, _ = StatisticRegistry(tmp_path).add(define_statistic(_count(), label="Boxes"))

        again, added = StatisticRegistry(tmp_path).add(define_statistic(_count(), label="Other label"))

        assert not added
        assert again == first
        assert len(StatisticRegistry(tmp_path).definitions()) == 1

    def test_a_level_is_a_statistic_of_its_own(self, tmp_path: Path) -> None:
        registry = StatisticRegistry(tmp_path)
        registry.add(define_statistic(_count(StatisticLevel.ENTITY), label="Boxes per object"))
        registry.add(define_statistic(_count(), label="Boxes per record"))

        assert [(definition.level, definition.label) for definition in registry.definitions()] == [
            (StatisticLevel.RECORD, "Boxes per record"),
            (StatisticLevel.ENTITY, "Boxes per object"),
        ]

    def test_a_name_held_by_other_choices_gets_a_column_of_its_own(self, tmp_path: Path) -> None:
        """Two values that differ by case alone make the same name: neither is refused."""
        registry = StatisticRegistry(tmp_path)
        upper, _ = registry.add(define_statistic(_count(attribute=AttributeFilter(field="category", value="Car"))))

        lower, added = registry.add(define_statistic(_count(attribute=AttributeFilter(field="category", value="car"))))

        assert added
        assert upper.name == "bbox_count_category_car"
        assert lower.name.startswith("bbox_count_category_car_")
        assert registry.get(StatisticLevel.RECORD, lower.name) == lower

    def test_a_value_typed_to_make_the_name_ended_with_a_hash_does_not_take_it(self, tmp_path: Path) -> None:
        registry = StatisticRegistry(tmp_path)
        lower = _count(attribute=AttributeFilter(field="category", value="car"))
        digest = hashlib.sha256(lower.model_dump_json().encode("utf-8")).hexdigest()[:8]
        registry.add(define_statistic(_count(attribute=AttributeFilter(field="category", value="Car"))))
        typed_value = AttributeFilter(field="category", value=f"car {digest}")
        typed, _ = registry.add(define_statistic(_count(attribute=typed_value)))

        third, added = registry.add(define_statistic(lower))

        assert added
        assert typed.name == f"bbox_count_category_car_{digest}"
        assert third.name == f"bbox_count_category_car_{digest}_2"

    def test_a_name_held_by_a_row_that_no_longer_reads_is_taken(self, tmp_path: Path) -> None:
        registry = StatisticRegistry(tmp_path)
        registry.add(define_statistic(_count(StatisticLevel.ENTITY)))
        broken = _row_of(define_statistic(_count())) | {"choices": '{"level": "nowhere"}'}
        _store(tmp_path).add(pa.Table.from_pylist([broken], schema=_SCHEMA))

        added, _ = registry.add(define_statistic(_count()))

        assert added.name.startswith("bbox_count_") and added.name != "bbox_count"

    def test_a_row_that_no_longer_reads_is_logged_once(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        registry = StatisticRegistry(tmp_path)
        registry.add(define_statistic(_count()))
        broken = _row_of(define_statistic(_count(StatisticLevel.ENTITY))) | {"choices": '{"level": "nowhere"}'}
        _store(tmp_path).add(pa.Table.from_pylist([broken], schema=_SCHEMA))

        with caplog.at_level(logging.WARNING, logger="pixano.statistics.registry"):
            registry.definitions()
            registry.definitions()

        assert len([record for record in caplog.records if "cannot be read" in record.getMessage()]) == 1

    def test_a_statistic_composed_at_once_by_two_requests_is_kept_once(self, tmp_path: Path) -> None:
        registry = StatisticRegistry(tmp_path)
        start = threading.Barrier(2)

        def compose() -> None:
            start.wait()
            registry.add(define_statistic(_count()))

        threads = [threading.Thread(target=compose) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert _store(tmp_path).count_rows() == 1

    def test_a_row_stored_twice_is_read_once(self, tmp_path: Path) -> None:
        registry = StatisticRegistry(tmp_path)
        first, _ = registry.add(define_statistic(_count()))
        _store(tmp_path).add(pa.Table.from_pylist([_row_of(define_statistic(_count()))], schema=_SCHEMA))

        assert registry.definitions() == [first]

    def test_a_row_that_no_longer_reads_as_a_statistic_is_left_out(self, tmp_path: Path) -> None:
        registry = StatisticRegistry(tmp_path)
        kept, _ = registry.add(define_statistic(_count()))
        broken = _row_of(define_statistic(_count(StatisticLevel.ENTITY))) | {"choices": '{"level": "nowhere"}'}
        _store(tmp_path).add(pa.Table.from_pylist([broken], schema=_SCHEMA))

        assert registry.definitions() == [kept]

    def test_a_measure_that_changed_composes_a_statistic_of_its_own(self, tmp_path, monkeypatch) -> None:
        registry = StatisticRegistry(tmp_path)
        before, _ = registry.add(define_statistic(_count()))
        monkeypatch.setitem(definitions_module.MEASURE_VERSIONS, StatisticMeasure.COUNT, 2)

        after, added = registry.add(define_statistic(_count()))

        assert added
        assert (before.name, after.name) == ("bbox_count", "bbox_count_v2")
        assert [definition.is_current for definition in registry.definitions()] == [False, True]

    def test_an_area_keeps_its_choices(self, tmp_path: Path) -> None:
        registry = StatisticRegistry(tmp_path)
        choices = StatisticChoices(
            level=StatisticLevel.RECORD,
            element="mask",
            measure=StatisticMeasure.AREA,
            aggregation=StatisticAggregation.MAX,
        )
        registry.add(define_statistic(choices))

        assert registry.definitions()[0].choices == choices
