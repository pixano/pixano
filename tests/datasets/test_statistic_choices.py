# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a dataset offers to compose a statistic from: what it holds, never a fixed list."""

import shutil
from pathlib import Path
from types import SimpleNamespace

from pydantic import create_model

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets import statistic_choices as choices_module
from pixano.datasets.statistic_choices import choices_for, statistic_applies
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Record
from pixano.statistics.definitions import (
    AttributeFilter,
    StatisticAggregation,
    StatisticChoices,
    StatisticLevel,
    StatisticMeasure,
)


VocEntity = create_model("VocEntity", __base__=Entity, category=(str, ""), color=(str, ""), is_difficult=(bool, False))


#: The categories of the dataset's objects, one object each: the last has none.
CATEGORIES = ("dog", "cat", "dog", "")


def _dataset(
    target: Path,
    entity: type[Entity] | None = VocEntity,
    categories: tuple[str, ...] = CATEGORIES,
    **slots,
) -> Dataset:
    info = DatasetInfo(id="ds", name="ds", record=Record, entity=entity, views={"image": Image}, **slots)
    dataset = Dataset.create(target / "ds", info)
    dataset.add_records({"records": [Record(id="r1")]})
    if entity is not None:
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
