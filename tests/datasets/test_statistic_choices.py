# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a dataset offers to compose a statistic from: what it holds, never a fixed list."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import create_model

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets import statistic_choices as choices_module
from pixano.datasets.statistic_choices import (
    choices_for,
    default_statistics,
    default_statistics_to_compute,
    statistic_applies,
)
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Record
from pixano.statistics.computed import ComputedStatistic
from pixano.statistics.definitions import (
    AttributeFilter,
    StatisticAggregation,
    StatisticChoices,
    StatisticLevel,
    StatisticMeasure,
    define_statistic,
)
from pixano.statistics.registry import StatisticRegistry


VocEntity = create_model("VocEntity", __base__=Entity, category=(str, ""), color=(str, ""), is_difficult=(bool, False))


#: The categories of the dataset's objects, one object each: the last has none.
CATEGORIES = ("dog", "cat", "dog", "")


#: When the statistics the tests hold were computed.
COMPUTED_AT = datetime(2026, 11, 10, tzinfo=timezone.utc)


def _with_boxes(dataset: Dataset) -> Dataset:
    """The dataset, a box drawn on its first object."""
    box = BBox(id="b0", record_id="r1", entity_id="e0", coords=[0, 0, 1, 1], format="xywh", is_normalized=True)
    dataset.add_data("bboxes", [box], raise_or_warn="none")
    return dataset


def _with_masks(dataset: Dataset) -> Dataset:
    """The dataset, a mask drawn on its first object."""
    mask = CompressedRLE.from_mask(np.ones((2, 2), dtype=np.uint8), id="m0", record_id="r1", entity_id="e0")
    dataset.add_data("masks", [mask], raise_or_warn="none")
    return dataset


def _dataset(
    target: Path,
    entity: type[Entity] | None = VocEntity,
    categories: tuple[str, ...] = CATEGORIES,
    **slots,
) -> Dataset:
    info = DatasetInfo(id="ds", name="ds", record=Record, entity=entity, views={"image": Image}, **slots)
    dataset = Dataset.create(target / "ds", info)
    dataset.add_records({"records": [Record(id="r1")]})
    if entity is not None and categories:
        entities = [
            entity(
                id=f"e{index}", record_id="r1", **({"category": category} if "category" in entity.model_fields else {})
            )
            for index, category in enumerate(categories)
        ]
        dataset.add_data("entities", entities, raise_or_warn="none")
    return dataset


class TestChoicesFor:
    def test_what_a_dataset_of_boxes_offers(self, tmp_path: Path) -> None:
        choices = choices_for(_dataset(tmp_path, bbox=BBox))

        assert [
            (element.element, element.levels, element.measures, element.reviewable) for element in choices.elements
        ] == [
            ("entity", [StatisticLevel.RECORD], [StatisticMeasure.COUNT], False),
            (
                "bbox",
                [StatisticLevel.RECORD, StatisticLevel.ENTITY],
                [StatisticMeasure.COUNT, StatisticMeasure.AREA, StatisticMeasure.IMAGE_RATIO],
                True,
            ),
        ]
        assert [(attribute.field, attribute.values) for attribute in choices.attributes] == [
            ("category", ["cat", "dog"]),
            ("color", []),
            ("is_difficult", ["true", "false"]),
        ]

    def test_a_dataset_of_masks_offers_no_box(self, tmp_path: Path) -> None:
        elements = [element.element for element in choices_for(_dataset(tmp_path, mask=CompressedRLE)).elements]

        assert elements == ["entity", "mask"]

    def test_a_dataset_without_objects_offers_records_alone_and_no_attribute(self, tmp_path: Path) -> None:
        choices = choices_for(_dataset(tmp_path, entity=None, bbox=BBox))

        assert [(element.element, element.levels) for element in choices.elements] == [
            ("bbox", [StatisticLevel.RECORD])
        ]
        assert choices.attributes == []

    def test_a_field_of_too_many_values_lists_its_first_and_says_so(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(choices_module, "MAX_ATTRIBUTE_VALUES", 1)

        category = choices_for(_dataset(tmp_path, bbox=BBox)).attributes[0]

        assert (category.values, category.values_complete) == (["cat"], False)

    def test_values_read_in_batches_are_the_first_in_alphabetical_order(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(choices_module, "_VALUES_BATCH_SIZE", 1)
        monkeypatch.setattr(choices_module, "MAX_ATTRIBUTE_VALUES", 2)
        dataset = _dataset(tmp_path, categories=("fox", "dog", "cat", "dog", "ant"), bbox=BBox)

        category = choices_for(dataset).attributes[0]

        assert (category.values, category.values_complete) == (["ant", "cat"], False)

    def test_as_many_values_as_listed_are_complete(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(choices_module, "_VALUES_BATCH_SIZE", 1)
        monkeypatch.setattr(choices_module, "MAX_ATTRIBUTE_VALUES", 2)

        category = choices_for(_dataset(tmp_path, bbox=BBox)).attributes[0]

        assert (category.values, category.values_complete) == (["cat", "dog"], True)

    def test_values_are_read_again_once_the_objects_are_written(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path, bbox=BBox)
        assert choices_for(dataset).attributes[0].values == ["cat", "dog"]

        dataset.add_data("entities", [VocEntity(id="e9", record_id="r1", category="bird")], raise_or_warn="none")

        assert choices_for(dataset).attributes[0].values == ["bird", "cat", "dog"]

    def test_values_are_read_again_once_the_dataset_is_made_again(self, tmp_path: Path) -> None:
        """A dataset made again under its identifier counts its tables' versions from the start."""
        assert choices_for(_dataset(tmp_path, bbox=BBox)).attributes[0].values == ["cat", "dog"]
        shutil.rmtree(tmp_path / "ds")

        again = _dataset(tmp_path, categories=("owl", "elk", "owl", ""), bbox=BBox)

        assert choices_for(again).attributes[0].values == ["elk", "owl"]

    def test_values_are_forgotten_when_the_dataset_changes_on_disk(self, tmp_path: Path) -> None:
        choices_for(_dataset(tmp_path, bbox=BBox))
        assert any(key[0] == "ds" for key in choices_module._values_cache)

        Dataset.invalidate_caches("ds")

        assert not any(key[0] == "ds" for key in choices_module._values_cache)


class TestStatisticApplies:
    def _choices(self, **changes) -> StatisticChoices:
        fields = {"level": StatisticLevel.RECORD, "element": "bbox", "measure": StatisticMeasure.COUNT} | changes
        return StatisticChoices(**fields)

    def test_to_a_dataset_that_holds_what_it_measures(self, tmp_path: Path) -> None:
        assert statistic_applies(self._choices(), _dataset(tmp_path, bbox=BBox))

    def test_not_to_a_dataset_without_it(self, tmp_path: Path) -> None:
        choices = self._choices(element="mask", measure=StatisticMeasure.AREA, aggregation=StatisticAggregation.MEAN)
        assert not statistic_applies(choices, _dataset(tmp_path, bbox=BBox))

    def test_not_per_object_to_a_dataset_without_objects(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path, entity=None, bbox=BBox)
        assert not statistic_applies(self._choices(level=StatisticLevel.ENTITY), dataset)

    def test_not_on_an_attribute_the_objects_lack(self, tmp_path: Path) -> None:
        choices = self._choices(attribute=AttributeFilter(field="size", value="large"))
        assert not statistic_applies(choices, _dataset(tmp_path, bbox=BBox))

    def test_on_a_yes_or_no_attribute_only_at_yes_or_no(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path, bbox=BBox)
        yes = AttributeFilter(field="is_difficult", value="true")
        assert statistic_applies(self._choices(attribute=yes), dataset)
        assert not statistic_applies(
            self._choices(attribute=AttributeFilter(field="is_difficult", value="dog")), dataset
        )

    def test_from_what_reads_a_dataset_as_the_worker_does(self) -> None:
        """The worker sees a dataset's tables through its reader, not a `Dataset`."""
        source = SimpleNamespace(
            info=SimpleNamespace(tables={"records": Record, "bboxes": BBox, "entities": VocEntity})
        )
        dogs = self._choices(attribute=AttributeFilter(field="category", value="dog"))

        assert statistic_applies(dogs, source)
        assert not statistic_applies(self._choices(element="mask"), source)


class TestDefaultStatistics:
    def test_a_dataset_of_objects_and_boxes_gets_those_that_count_them(self, tmp_path: Path) -> None:
        dataset = _with_boxes(_dataset(tmp_path, bbox=BBox))

        assert [(statistic.level.value, statistic.name) for statistic in default_statistics(dataset)] == [
            ("record", "entity_count"),
            ("record", "bbox_count"),
            ("entity", "bbox_to_image_ratio_mean"),
        ]

    def test_a_dataset_of_masks_counts_its_masks_and_no_box(self, tmp_path: Path) -> None:
        dataset = _with_masks(_dataset(tmp_path, mask=CompressedRLE))

        assert [statistic.name for statistic in default_statistics(dataset)] == ["entity_count", "mask_count"]

    def test_a_dataset_without_objects_nor_annotations_gets_none(self, tmp_path: Path) -> None:
        assert default_statistics(_dataset(tmp_path, entity=None)) == []

    def test_a_table_declared_without_a_row_counts_nothing_yet(self, tmp_path: Path) -> None:
        """An import of images alone declares a table of objects and one of boxes, both empty."""
        dataset = _dataset(tmp_path, categories=(), bbox=BBox, mask=CompressedRLE)

        assert default_statistics(dataset) == []

    def test_those_computed_are_no_longer_to_compute(self, tmp_path: Path) -> None:
        dataset = _with_boxes(_dataset(tmp_path, bbox=BBox))
        objects = default_statistics(dataset)[0]
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {objects.name: "int"})
        dataset.record_computed_statistics(
            [ComputedStatistic(definition=objects, job_id="j", computed_at=COMPUTED_AT)]
        )

        assert [statistic.name for statistic in default_statistics_to_compute(dataset)] == [
            "bbox_count",
            "bbox_to_image_ratio_mean",
        ]

    def test_the_label_the_dataset_gave_one_stays(self, tmp_path: Path) -> None:
        dataset = _with_boxes(_dataset(tmp_path, bbox=BBox))
        objects = default_statistics(dataset)[0].model_copy(update={"label": "Animals"})
        dataset.ensure_statistic_columns(StatisticLevel.RECORD, {objects.name: "int"})
        dataset.record_computed_statistics(
            [ComputedStatistic(definition=objects, job_id="j", computed_at=COMPUTED_AT)]
        )

        assert default_statistics(dataset)[0].label == "Animals"

    def test_the_label_the_library_gave_one_stays_where_the_dataset_holds_none(self, tmp_path: Path) -> None:
        dataset = _with_boxes(_dataset(tmp_path, bbox=BBox))
        boxes = default_statistics(dataset)[1]
        registry = StatisticRegistry(tmp_path)
        registry.add(define_statistic(boxes.choices, label="Boxes drawn"))

        assert [statistic.label for statistic in default_statistics_to_compute(dataset, registry)][1] == "Boxes drawn"

    def test_a_statistic_of_an_earlier_version_of_its_measure_keeps_no_label(self, tmp_path: Path) -> None:
        dataset = _with_boxes(_dataset(tmp_path, bbox=BBox))
        objects = default_statistics(dataset)[0].model_copy(update={"label": "Animals", "version": 0})
        dataset.record_computed_statistics(
            [ComputedStatistic(definition=objects, job_id="j", computed_at=COMPUTED_AT)]
        )

        assert default_statistics(dataset)[0].label == "Number of objects"
