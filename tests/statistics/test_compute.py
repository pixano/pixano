# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The values of statistics, from what a record holds: counts, areas, shares, and what filters keep."""

import numpy as np
import pytest
from pydantic import create_model

from pixano.schemas import BBox, CompressedRLE, Entity, ReviewStatus
from pixano.statistics.compute import RecordContent, compute_values
from pixano.statistics.definitions import (
    AnnotationOrigin,
    AttributeFilter,
    StatisticAggregation,
    StatisticChoices,
    StatisticLevel,
    StatisticMeasure,
    define_statistic,
)


VocEntity = create_model("VocEntity", __base__=Entity, category=(str, ""), is_difficult=(bool, False))
IMAGE_SIZE = (200, 100)


def _box(box_id: str, entity_id: str, coords: list[float], normalized: bool = True, **row) -> BBox:
    return BBox(
        id=box_id,
        entity_id=entity_id,
        view_id="image-1",
        coords=coords,
        format="xywh",
        is_normalized=normalized,
        **row,
    )


def _mask(mask_id: str, entity_id: str, filled: int) -> CompressedRLE:
    """A mask of 4 × 5 pixels, its first `filled` pixels set, column by column."""
    pixels = np.zeros(20, dtype=np.uint8)
    pixels[:filled] = 1
    return CompressedRLE.from_mask(pixels.reshape(5, 4).T.copy(), id=mask_id, entity_id=entity_id)


def _grid(mask: CompressedRLE) -> tuple[int, int, int] | None:
    """The grid and painted pixels of a mask well formed, as the worker reads them once checked."""
    height, width = mask.size
    return height, width, int(mask.area)


def _content(boxes=(), masks=(), entities=None, image_size=IMAGE_SIZE, mask_grid=_grid) -> RecordContent:
    if entities is None:
        entities = [
            VocEntity(id="dog-1", record_id="r1", category="dog"),
            VocEntity(id="cat-1", record_id="r1", category="cat", is_difficult=True),
            VocEntity(id="part-1", record_id="r1", category="dog", parent_id="dog-1"),
        ]
    return RecordContent(
        record_id="r1",
        entities=entities,
        annotations={"bbox": list(boxes), "mask": list(masks)},
        image_size=lambda view_id: image_size,
        mask_grid=mask_grid,
    )


def _values(choices: StatisticChoices, content: RecordContent):
    definition = define_statistic(choices)
    computed = compute_values([definition], content)
    if choices.level is StatisticLevel.RECORD:
        return computed.record[definition.name]
    return {entity: values[definition.name] for entity, values in computed.entities.items()}


def _record(**changes) -> StatisticChoices:
    return StatisticChoices(
        **({"level": StatisticLevel.RECORD, "element": "bbox", "measure": StatisticMeasure.COUNT} | changes)
    )


BOXES = [
    _box("b1", "dog-1", [0.0, 0.0, 0.5, 0.5], source_type="model", review_status="pending"),
    _box("b2", "dog-1", [0.0, 0.0, 0.1, 0.2], source_type="model", review_status="accepted"),
    _box("b3", "cat-1", [0.0, 0.0, 0.2, 0.5], source_type="other"),
]


class TestCount:
    def test_the_boxes_of_a_record(self) -> None:
        assert _values(_record(), _content(BOXES)) == 3

    def test_none_is_zero(self) -> None:
        assert _values(_record(), _content()) == 0

    def test_the_objects_a_person_sees_leave_their_parts_out(self) -> None:
        assert _values(_record(element="entity"), _content()) == 2

    def test_the_objects_of_a_class(self) -> None:
        dogs = _record(element="entity", attribute=AttributeFilter(field="category", value="dog"))
        assert _values(dogs, _content()) == 1

    def test_the_boxes_of_a_class(self) -> None:
        dogs = _record(attribute=AttributeFilter(field="category", value="dog"))
        assert _values(dogs, _content(BOXES)) == 2

    def test_on_a_yes_or_no_attribute(self) -> None:
        difficult = _record(attribute=AttributeFilter(field="is_difficult", value="true"))
        assert _values(difficult, _content(BOXES)) == 1

    def test_by_origin(self) -> None:
        assert _values(_record(origin=AnnotationOrigin.MODEL), _content(BOXES)) == 2
        assert _values(_record(origin=AnnotationOrigin.NOT_MODEL), _content(BOXES)) == 1

    def test_by_review_status_a_model_row_without_one_reading_pending(self) -> None:
        unreviewed = _box("b4", "cat-1", [0.0, 0.0, 0.1, 0.1], source_type="model", review_status="")
        content = _content([*BOXES, unreviewed])

        assert _values(_record(review_status=ReviewStatus.PENDING), content) == 2
        assert _values(_record(review_status=ReviewStatus.ACCEPTED), content) == 1


class TestArea:
    def _area(self, aggregation: StatisticAggregation, **changes) -> StatisticChoices:
        return _record(measure=StatisticMeasure.AREA, aggregation=aggregation, **changes)

    def test_of_normalized_boxes_in_pixels(self) -> None:
        # 100 by 50, 20 by 20, 40 by 50 pixels, on an image of 200 by 100.
        assert _values(self._area(StatisticAggregation.SUM), _content(BOXES)) == pytest.approx(5000 + 400 + 2000)
        assert _values(self._area(StatisticAggregation.MAX), _content(BOXES)) == pytest.approx(5000)
        assert _values(self._area(StatisticAggregation.MIN), _content(BOXES)) == pytest.approx(400)
        assert _values(self._area(StatisticAggregation.MEAN), _content(BOXES)) == pytest.approx(7400 / 3)

    def test_of_boxes_in_pixels_already(self) -> None:
        box = _box("b1", "dog-1", [10, 10, 30, 20], normalized=False)
        assert _values(self._area(StatisticAggregation.SUM), _content([box], image_size=None)) == pytest.approx(600)

    def test_of_a_box_whose_geometry_is_no_area_leaves_it_out(self) -> None:
        """A box takes an infinite coordinate: no area is infinite."""
        boxes = [
            _box("b1", "dog-1", [0.0, 0.0, 10.0, 20.0], normalized=False),
            _box("b2", "dog-1", [0.0, 0.0, float("inf"), 20.0], normalized=False),
        ]

        assert _values(self._area(StatisticAggregation.MAX), _content(boxes=boxes)) == 200.0

    def test_of_normalized_boxes_on_an_image_of_unknown_size_is_none(self) -> None:
        assert _values(self._area(StatisticAggregation.MEAN), _content(BOXES, image_size=None)) is None
        assert _values(self._area(StatisticAggregation.SUM), _content(BOXES, image_size=None)) is None

    def test_of_nothing_is_none_but_a_sum_of_nothing_is_zero(self) -> None:
        assert _values(self._area(StatisticAggregation.MEAN), _content()) is None
        assert _values(self._area(StatisticAggregation.SUM), _content()) == 0.0

    def test_of_masks_from_their_pixels(self) -> None:
        masks = [_mask("m1", "dog-1", 6), _mask("m2", "cat-1", 2)]
        assert _values(self._area(StatisticAggregation.MAX, element="mask"), _content(masks=masks)) == 6.0

    def test_of_a_mask_that_cannot_be_read_safely_leaves_it_out(self) -> None:
        masks = [_mask("m1", "dog-1", 6), _mask("m2", "cat-1", 2)]

        def unreadable_first(mask: CompressedRLE) -> tuple[int, int, int] | None:
            return None if mask.id == "m1" else _grid(mask)

        content = _content(masks=masks, mask_grid=unreadable_first)
        assert _values(self._area(StatisticAggregation.MAX, element="mask"), content) == 2.0


class TestShareOfTheImage:
    def _share(self, aggregation: StatisticAggregation, **changes) -> StatisticChoices:
        return _record(measure=StatisticMeasure.IMAGE_RATIO, aggregation=aggregation, **changes)

    def test_of_normalized_boxes_needs_no_size(self) -> None:
        assert _values(self._share(StatisticAggregation.MAX), _content(BOXES, image_size=None)) == pytest.approx(0.25)

    def test_of_boxes_in_pixels(self) -> None:
        box = _box("b1", "dog-1", [0, 0, 100, 50], normalized=False)
        assert _values(self._share(StatisticAggregation.MAX), _content([box])) == pytest.approx(0.25)

    def test_of_masks(self) -> None:
        masks = [_mask("m1", "dog-1", 5)]
        assert _values(self._share(StatisticAggregation.MEAN, element="mask"), _content(masks=masks)) == pytest.approx(
            0.25
        )


class TestPerObject:
    def test_each_object_counts_its_own(self) -> None:
        per_object = _record(level=StatisticLevel.ENTITY)
        assert _values(per_object, _content(BOXES)) == {"dog-1": 2, "cat-1": 1, "part-1": 0}

    def test_an_object_without_the_attribute_has_no_value(self) -> None:
        dogs = _record(level=StatisticLevel.ENTITY, attribute=AttributeFilter(field="category", value="dog"))
        assert _values(dogs, _content(BOXES)) == {"dog-1": 2, "cat-1": None, "part-1": 0}

    def test_the_area_of_an_objects_boxes(self) -> None:
        mean_area = _record(
            level=StatisticLevel.ENTITY, measure=StatisticMeasure.AREA, aggregation=StatisticAggregation.MEAN
        )
        assert _values(mean_area, _content(BOXES)) == {
            "dog-1": pytest.approx((5000 + 400) / 2),
            "cat-1": pytest.approx(2000),
            "part-1": None,
        }
