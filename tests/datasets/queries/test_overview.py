# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A dataset's overview: its cards, over the records a request keeps, counted per split if asked."""

from pathlib import Path

import pytest
from pydantic import create_model

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.queries.computed_columns import ComputedFilter, CrossFilter
from pixano.datasets.queries.overview import BARS, OverviewCard, dataset_overview
from pixano.datasets.statistic_choices import default_statistics
from pixano.schemas import BBox, Image, Record
from pixano.statistics.computed import ComputedStatistic
from pixano.statistics.definitions import StatisticLevel
from tests.fixtures.overview import (
    COMPUTED_AT,
    OBJECTS_PER_RECORD,
    ClassedEntity,
    WeatherRecord,
    build_overview_dataset,
)


EVERY_RECORD = CrossFilter()
#: The records of more than one object, as the explorer's filter `record_statistics.entity_count:gte:2` asks.
TWO_OBJECTS = ComputedFilter(sql='c."entity_count" >= 2', columns=("entity_count",))


@pytest.fixture
def dataset(tmp_path: Path) -> Dataset:
    return build_overview_dataset(tmp_path)


def _cards(overview) -> dict[str, OverviewCard]:  # noqa: ANN001 - a DatasetOverview
    return {card.id: card for card in overview.cards}


def _values(card: OverviewCard) -> dict[str, int]:
    return {value.value: value.count for value in card.values}


def _bars(card: OverviewCard) -> list[tuple[float, int]]:
    return [(bar.start, bar.count) for bar in card.bars if bar.count]


def _count_at(card: OverviewCard, value: float) -> int:
    """The count of the bar holding a value: wide ranges are cut into bars of several values."""
    last = len(card.bars) - 1
    return next(
        (
            bar.count
            for index, bar in enumerate(card.bars)
            if bar.start <= value < bar.end or (index == last and value == bar.end)
        ),
        0,
    )


def _dataset_of(tmp_path: Path, record: type[Record], records: list[Record], **tables: type) -> Dataset:
    """A dataset of these records, with these tables declared."""
    info = DatasetInfo(id="other", name="other", record=record, **tables)
    dataset = Dataset.create(tmp_path / "other", info)
    if records:
        dataset.add_records({"records": records})
    return dataset


def _measured(tmp_path: Path, ratios: list[float]) -> Dataset:
    """A dataset of records holding a number that is not whole each."""
    Measured = create_model("Measured", __base__=Record, ratio=(float, 0.0))
    return _dataset_of(
        tmp_path, Measured, [Measured(id=f"r{index}", ratio=ratio) for index, ratio in enumerate(ratios)]
    )


class TestTheCards:
    def test_come_records_first_then_media_then_annotations(self, dataset: Dataset) -> None:
        overview = dataset_overview(dataset, EVERY_RECORD)

        groups = [card.group for card in overview.cards]
        assert groups == sorted(groups, key=("records", "media", "annotations").index)
        assert (overview.records, overview.total_records) == (4, 4)

    def test_a_text_field_counts_its_values_the_most_held_first_and_an_empty_one_as_missing(
        self, dataset: Dataset
    ) -> None:
        weather = _cards(dataset_overview(dataset, EVERY_RECORD))["field:weather"]

        assert (weather.kind, weather.filter_column, weather.subject) == ("values", "weather", "record")
        assert [(value.value, value.count) for value in weather.values] == [("rain", 2), ("sun", 1)]
        assert (weather.population, weather.missing, weather.distinct, weather.others) == (4, 1, 2, 0)
        assert weather.filtered is False and all(value.selected is None for value in weather.values)

    def test_a_yes_or_no_field_counts_true_and_false(self, dataset: Dataset) -> None:
        sunny = _cards(dataset_overview(dataset, EVERY_RECORD))["field:sunny"]

        assert _values(sunny) == {"false": 3, "true": 1}

    def test_a_number_field_is_a_histogram_with_its_summary(self, dataset: Dataset) -> None:
        rank = _cards(dataset_overview(dataset, EVERY_RECORD))["field:rank"]

        assert (rank.kind, rank.whole_values, rank.label) == ("histogram", True, "Rank")
        assert (rank.minimum, rank.maximum, rank.mean, rank.median) == (1, 4, 2.5, 2.5)
        assert [(bar.start, bar.end, bar.count) for bar in rank.bars] == [(1, 2, 1), (2, 3, 1), (3, 4, 1), (4, 5, 1)]

    def test_the_identifier_the_timestamps_and_the_annotators_note_have_no_card(self, dataset: Dataset) -> None:
        ids = set(_cards(dataset_overview(dataset, EVERY_RECORD)))

        assert {"field:id", "field:created_at", "field:updated_at", "field:comment"}.isdisjoint(ids)
        assert {"field:split", "field:status"} <= ids

    def test_a_statistic_per_record_filters_the_records_on_its_column_and_says_when_it_was_computed(
        self, dataset: Dataset
    ) -> None:
        objects = _cards(dataset_overview(dataset, EVERY_RECORD))["statistic:entity_count"]

        assert (objects.label, objects.filter_column, objects.group) == (
            "Number of objects",
            "record_statistics.entity_count",
            "annotations",
        )
        assert _bars(objects) == [(0, 1), (1, 2), (2, 1)]
        assert objects.computed_at == COMPUTED_AT

    def test_the_images_size_aspect_ratio_and_format_from_their_metadata(self, dataset: Dataset) -> None:
        cards = _cards(dataset_overview(dataset, EVERY_RECORD))

        width = cards["image:images:width"]
        assert (_count_at(width, 320), _count_at(width, 640), width.filter_column) == (1, 2, None)
        assert cards["image:images:aspect_ratio"].minimum == 1
        assert cards["image:images:aspect_ratio"].maximum == pytest.approx(640 / 480)
        assert _values(cards["image:images:format"]) == {"jpeg": 2, "png": 1}
        assert width.computed_at is None

    def test_images_per_record_count_a_record_without_any(self, dataset: Dataset) -> None:
        per_record = _cards(dataset_overview(dataset, EVERY_RECORD))["image:images:per_record"]

        assert (per_record.population, _bars(per_record)) == (4, [(0, 1), (1, 3)])

    def test_the_objects_by_class_and_their_statistics(self, dataset: Dataset) -> None:
        cards = _cards(dataset_overview(dataset, EVERY_RECORD))

        assert _values(cards["object:class"]) == {"dog": 2, "cat": 1, "bird": 1}
        share = cards["object_statistic:bbox_to_image_ratio_mean"]
        assert (share.subject, share.population, share.minimum, share.maximum) == ("object", 4, 0.05, 0.5)
        assert share.computed_at == COMPUTED_AT

    def test_a_card_of_many_values_lists_the_most_held_and_counts_the_others(
        self, dataset: Dataset, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pixano.datasets.queries import overview as overview_module

        monkeypatch.setattr(overview_module, "MAX_LISTED_VALUES", 1)

        weather = _cards(dataset_overview(dataset, EVERY_RECORD))["field:weather"]

        assert ([value.value for value in weather.values], weather.others) == (["rain"], 1)


class TestTheObjects:
    def test_an_object_created_since_the_statistics_counts_as_without_a_value(self, dataset: Dataset) -> None:
        dataset.add_data("entities", [ClassedEntity(id="e5", record_id="r4", category="cat")], raise_or_warn="none")

        cards = _cards(dataset_overview(dataset, EVERY_RECORD))

        share = cards["object_statistic:bbox_to_image_ratio_mean"]
        assert (share.population, share.missing) == (5, 1)
        assert _values(cards["object:class"]) == {"dog": 2, "cat": 2, "bird": 1}

    def test_the_values_of_an_object_deleted_since_are_not_read(self, dataset: Dataset) -> None:
        dataset.delete_data("entities", ["e3"])

        share = _cards(dataset_overview(dataset, EVERY_RECORD))["object_statistic:bbox_to_image_ratio_mean"]

        assert (share.population, share.maximum) == (3, 0.2)

    def test_an_object_part_of_another_is_not_counted_as_the_number_of_objects_does_not_count_it(
        self, dataset: Dataset
    ) -> None:
        part = ClassedEntity(id="e1-part", record_id="r1", parent_id="e1", category="paw")
        dataset.add_data("entities", [part], raise_or_warn="none")

        classes = _cards(dataset_overview(dataset, EVERY_RECORD))["object:class"]

        assert "paw" not in _values(classes)
        assert sum(_values(classes).values()) == sum(OBJECTS_PER_RECORD.values())


def _kept_by_bar(card: OverviewCard, values: list[float]) -> list[int]:
    """How many of these values each bar's filter keeps, as the interface writes it: from its start, to
    its end left out, or kept for the last bar.
    """
    last = len(card.bars) - 1
    return [
        sum(1 for value in values if bar.start <= value and (value <= bar.end if index == last else value < bar.end))
        for index, bar in enumerate(card.bars)
    ]


class TestTheBars:
    def test_each_bar_counts_the_values_its_filter_keeps_those_on_an_edge_included(self, tmp_path: Path) -> None:
        """0.85 among bars of 0.05 from 0 lies on an edge that division puts in the bar before."""
        ratios = [0.0, 0.05, 0.1, 0.15, 0.3, 0.35, 0.55, 0.6, 0.7, 0.85, 0.9, 0.95, 1.0]

        ratio = _cards(dataset_overview(_measured(tmp_path, ratios), EVERY_RECORD))["field:ratio"]

        assert [bar.count for bar in ratio.bars] == _kept_by_bar(ratio, ratios)

    def test_numbers_that_are_not_whole_are_cut_into_bars_the_last_ending_at_the_largest(self, tmp_path: Path) -> None:
        ratios = [0.1, 0.2, 0.3, 0.7, 1 / 3]

        ratio = _cards(dataset_overview(_measured(tmp_path, ratios), EVERY_RECORD))["field:ratio"]

        assert (len(ratio.bars), ratio.bars[0].start, ratio.bars[-1].end) == (BARS, 0.1, 0.7)
        assert sum(bar.count for bar in ratio.bars) == len(ratios)
        assert (ratio.bars[0].count, ratio.bars[-1].count) == (1, 1)

    def test_one_value_alone_makes_one_bar_from_it_to_it(self, tmp_path: Path) -> None:
        ratio = _cards(dataset_overview(_measured(tmp_path, [0.25] * 3), EVERY_RECORD))["field:ratio"]

        assert [(bar.start, bar.end, bar.count) for bar in ratio.bars] == [(0.25, 0.25, 3)]

    def test_the_smallest_value_falls_in_the_first_bar_whatever_its_digits(self, tmp_path: Path) -> None:
        """A share of seventeen digits read back must not fall before the first bar, into the last.

        Written in a query as a literal, DuckDB reads this smallest value back a bit larger than it is.
        """
        ratios = [0.17151709517771863, 0.49649365599282835, 0.9]

        ratio = _cards(dataset_overview(_measured(tmp_path, ratios), EVERY_RECORD))["field:ratio"]

        assert (ratio.bars[0].count, ratio.bars[-1].count) == (1, 1)

    def test_whole_values_of_a_wide_range_get_bars_of_several_values_the_last_ending_after_the_largest(
        self, tmp_path: Path
    ) -> None:
        Ranked = create_model("Ranked", __base__=Record, rank=(int, 0))
        dataset = _dataset_of(tmp_path, Ranked, [Ranked(id=f"r{rank}", rank=rank) for rank in (0, 20, 40)])

        rank = _cards(dataset_overview(dataset, EVERY_RECORD))["field:rank"]

        # Forty-one values in bars of three: fourteen bars, the last holding 39 and 40 only.
        assert (len(rank.bars), rank.bars[0].end - rank.bars[0].start) == (14, 3)
        assert (rank.bars[-1].start, rank.bars[-1].end, rank.bars[-1].count) == (39, 41, 1)

    def test_a_number_that_is_not_finite_counts_as_missing(self, tmp_path: Path) -> None:
        ratio = _cards(dataset_overview(_measured(tmp_path, [0.5, float("nan"), float("inf")]), EVERY_RECORD))[
            "field:ratio"
        ]

        assert (ratio.population, ratio.missing, ratio.minimum, ratio.maximum) == (3, 2, 0.5, 0.5)

    def test_an_image_of_size_zero_has_no_size(self, tmp_path: Path) -> None:
        dataset = _dataset_of(tmp_path, Record, [], views={"image": Image})
        dataset.add_records(
            {
                "records": [Record(id="r1"), Record(id="r2")],
                "images": [
                    Image(id="i1", record_id="r1", logical_name="image", url="1.jpg", width=0, height=0, format=""),
                    Image(id="i2", record_id="r2", logical_name="image", url="2.jpg", width=8, height=4, format="png"),
                ],
            }
        )

        cards = _cards(dataset_overview(dataset, EVERY_RECORD))

        assert (cards["image:images:width"].missing, cards["image:images:aspect_ratio"].missing) == (1, 1)
        assert (cards["image:images:format"].missing, cards["image:images:aspect_ratio"].maximum) == (1, 2)


class TestTheRecordsKept:
    def test_every_card_counts_only_the_records_a_condition_keeps(self, dataset: Dataset) -> None:
        cards = _cards(dataset_overview(dataset, CrossFilter(where="split = 'train'")))

        assert cards["field:weather"].population == 2
        assert _values(cards["object:class"]) == {"dog": 2, "cat": 1}
        assert [_count_at(cards["image:images:width"], width) for width in (320, 640)] == [0, 2]

    def test_a_condition_on_a_computed_column_without_a_card_keeps_the_records_through_the_join(
        self, dataset: Dataset
    ) -> None:
        dataset.info.statistics = []

        overview = dataset_overview(dataset, CrossFilter(on_computed={"record_statistics.entity_count": TWO_OBJECTS}))

        assert overview.records == 1
        assert _values(_cards(overview)["object:class"]) == {"dog": 1, "cat": 1}

    def test_a_field_of_the_same_name_as_a_statistic_keeps_its_own_card(self, tmp_path: Path) -> None:
        Counted = create_model("Counted", __base__=Record, entity_count=(int, 0))
        dataset = _dataset_of(tmp_path, Counted, [Counted(id="r1", entity_count=7)], entity=ClassedEntity)
        dataset.add_data("entities", [ClassedEntity(id="e1", record_id="r1")], raise_or_warn="none")
        (statistic,) = default_statistics(dataset)
        columns = {statistic.name: "int"}
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, columns)
        dataset.write_statistic_values(StatisticLevel.RECORD, [{"record_id": "r1", statistic.name: 1}], columns)
        dataset.record_computed_statistics(
            [ComputedStatistic(definition=statistic, job_id="job-1", computed_at=COMPUTED_AT)]
        )

        cards = _cards(dataset_overview(dataset, EVERY_RECORD))

        assert (cards["field:entity_count"].minimum, cards["statistic:entity_count"].minimum) == (7, 1)


class TestCrossFiltering:
    def test_the_free_text_applies_to_a_card_of_a_column_filtered_too(self, dataset: Dataset) -> None:
        cross_filter = CrossFilter(where="rank >= 2", on_records={"weather": "weather = 'rain'"})

        weather = _cards(dataset_overview(dataset, cross_filter))["field:weather"]

        # r1 is left out by the free text, whatever its weather: r2 sun, r3 rain, r4 none.
        assert (weather.population, _values(weather)) == (3, {"rain": 1, "sun": 1})

    def test_a_card_of_a_column_filtered_counts_the_records_its_filters_leave_and_tells_those_they_keep(
        self, dataset: Dataset
    ) -> None:
        overview = dataset_overview(dataset, CrossFilter(on_records={"weather": "weather = 'rain'"}))
        cards = _cards(overview)

        weather = cards["field:weather"]
        assert (weather.filtered, weather.population) == (True, 4)
        assert {value.value: (value.count, value.selected) for value in weather.values} == {
            "rain": (2, 2),
            "sun": (1, 0),
        }
        rank = cards["field:rank"]
        assert (overview.records, rank.filtered, rank.population) == (2, False, 2)
        assert all(bar.selected is None for bar in rank.bars)

    def test_each_filtered_card_leaves_out_its_own_filters_alone(self, dataset: Dataset) -> None:
        cross_filter = CrossFilter(
            on_records={"weather": "weather = 'rain'", "split": "split = 'train'"},
            on_computed={"record_statistics.entity_count": TWO_OBJECTS},
        )

        cards = _cards(dataset_overview(dataset, cross_filter))

        # In train, of two objects: r1 alone, whose weather is rain.
        assert _values(cards["field:weather"]) == {"rain": 1}
        # Rain, of two objects: r1 alone, in train.
        assert _values(cards["field:split"]) == {"train": 1}
        # Rain in train: r1 alone, of two objects.
        objects = cards["statistic:entity_count"]
        assert (objects.filtered, objects.population) == (True, 1)
        assert [(bar.start, bar.count, bar.selected) for bar in objects.bars if bar.count] == [(2, 1, 1)]
        assert _values(cards["object:class"]) == {"dog": 1, "cat": 1}

    def test_a_statistic_card_filtered_shows_its_whole_distribution_its_kept_bars_told(self, dataset: Dataset) -> None:
        cross_filter = CrossFilter(on_computed={"record_statistics.entity_count": TWO_OBJECTS})

        cards = _cards(dataset_overview(dataset, cross_filter))

        objects = cards["statistic:entity_count"]
        assert [(bar.start, bar.count, bar.selected) for bar in objects.bars] == [(0, 1, 0), (1, 2, 0), (2, 1, 1)]
        assert cards["field:weather"].population == 1

    def test_the_others_of_a_card_of_values_tell_those_they_keep(
        self, dataset: Dataset, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pixano.datasets.queries import overview as overview_module

        monkeypatch.setattr(overview_module, "MAX_LISTED_VALUES", 1)

        overview = dataset_overview(dataset, CrossFilter(on_records={"weather": "weather = 'sun'"}))
        weather = _cards(overview)["field:weather"]

        assert ([(value.value, value.selected) for value in weather.values], weather.others) == ([("rain", 0)], 1)
        assert weather.others_selected == 1


class TestPerSplit:
    def test_each_card_counts_its_values_per_split_and_what_a_share_is_counted_out_of(self, dataset: Dataset) -> None:
        overview = dataset_overview(dataset, EVERY_RECORD, by_split=True)
        cards = _cards(overview)

        assert overview.splits == ["test", "train", "val"]
        classes = {value.value: value.by_split for value in cards["object:class"].values}
        assert classes == {"dog": {"train": 2}, "cat": {"train": 1}, "bird": {"val": 1}}
        assert cards["object:class"].counted_by_split == {"train": 3, "val": 1}
        objects = cards["statistic:entity_count"]
        assert {bar.start: bar.by_split for bar in objects.bars if bar.count} == {
            0: {"test": 1},
            1: {"train": 1, "val": 1},
            2: {"train": 1},
        }

    def test_the_values_not_listed_are_counted_per_split_too(
        self, dataset: Dataset, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pixano.datasets.queries import overview as overview_module

        monkeypatch.setattr(overview_module, "MAX_LISTED_VALUES", 1)

        classes = _cards(dataset_overview(dataset, EVERY_RECORD, by_split=True))["object:class"]

        assert [(value.value, value.by_split) for value in classes.values] == [("dog", {"train": 2})]
        assert classes.others_by_split == {"train": 1, "val": 1}

    def test_without_asking_no_card_counts_per_split_but_the_splits_are_told(self, dataset: Dataset) -> None:
        overview = dataset_overview(dataset, EVERY_RECORD)

        assert overview.splits == ["test", "train", "val"]
        assert all(not card.counted_by_split for card in overview.cards)

    def test_the_splits_are_those_of_every_record_a_card_counts(self, dataset: Dataset) -> None:
        overview = dataset_overview(dataset, CrossFilter(on_records={"split": "split = 'val'"}))

        assert (overview.records, overview.splits) == (1, ["test", "train", "val"])


class TestEmptyDatasets:
    def test_a_dataset_without_records_has_cards_without_values(self, tmp_path: Path) -> None:
        dataset = _dataset_of(tmp_path, WeatherRecord, [], entity=ClassedEntity, views={"image": Image})

        overview = dataset_overview(dataset, EVERY_RECORD)

        assert (overview.records, overview.splits) == (0, [])
        assert all(card.population == 0 and not card.bars and not card.values for card in overview.cards)

    def test_a_dataset_without_images_nor_objects_has_its_records_cards_alone(self, tmp_path: Path) -> None:
        dataset = _dataset_of(tmp_path, Record, [Record(id="r1", split="train")])

        overview = dataset_overview(dataset, EVERY_RECORD)

        assert {card.group for card in overview.cards} == {"records"}
        assert overview.statistics_to_compute == []


class TestTheStatisticsToCompute:
    def test_a_dataset_that_computed_its_defaults_has_none_to_compute(self, dataset: Dataset) -> None:
        assert dataset_overview(dataset, EVERY_RECORD).statistics_to_compute == []

    def test_a_dataset_just_imported_has_its_defaults_to_compute_and_no_card_of_them(self, tmp_path: Path) -> None:
        dataset = _dataset_of(tmp_path, Record, [Record(id="r1")], entity=ClassedEntity, views={"image": Image})
        dataset.add_data("entities", [ClassedEntity(id="e1", record_id="r1")], raise_or_warn="none")

        overview = dataset_overview(dataset, EVERY_RECORD)

        assert [statistic.name for statistic in overview.statistics_to_compute] == ["entity_count"]
        assert not any(card.id.startswith("statistic:") for card in overview.cards)

    def test_an_import_of_images_alone_has_nothing_to_compute_as_the_import_queues_nothing(
        self, tmp_path: Path
    ) -> None:
        """Its tables of objects and boxes are declared, and empty."""
        dataset = _dataset_of(
            tmp_path, Record, [Record(id="r1")], entity=ClassedEntity, bbox=BBox, views={"image": Image}
        )

        assert dataset_overview(dataset, EVERY_RECORD).statistics_to_compute == []
