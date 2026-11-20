# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The values of statistics, computed from what a record holds (backend-processing §22).

Pure: a record's objects and annotations come in, the values of each statistic come out, for the
record and for each of its objects. The job that computes statistics reads and writes; this
computes, the same way whoever calls it.

What a value is:

- a **count** is a whole number, zero when nothing is kept;
- an **area** or a **share of the image** is the aggregation of the values of the annotations kept:
  none when there is no value to aggregate, but a sum of nothing kept is zero;
- per object, a statistic whose attribute the object does not have is no value, not zero: the
  statistic does not apply to it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from statistics import fmean
from typing import Any

from pixano.schemas import AnnotationSourceKind, stored_statuses

from .definitions import (
    ENTITY_ELEMENT,
    MASK_ELEMENT,
    AnnotationOrigin,
    StatisticAggregation,
    StatisticChoices,
    StatisticDefinition,
    StatisticLevel,
    StatisticMeasure,
)


#: A statistic's value: whole for a count, decimal for an area or a share, None where there is none.
StatisticValue = int | float | None

#: A mask's grid, height then width, and how many pixels it paints; None when it cannot be read
#: safely, and nothing is measured from it.
MaskReader = Callable[[Any], tuple[int, int, int] | None]

_MODEL_SOURCE = AnnotationSourceKind.MODEL.value


@dataclass(frozen=True)
class RecordContent:
    """What a record holds that statistics measure.

    Attributes:
        record_id: The record.
        entities: Its objects, of the dataset's entity schema.
        annotations: Its annotations, by `DatasetInfo` slot.
        image_size: The width and height in pixels of a view, by its identifier; None when the size
            is unknown, and the areas that need it are then left out. A box is measured against
            the view it is drawn on: its frame when it names one (`frame_id`), else its view.
        mask_grid: How a mask is read: its grid and painted pixels, None when it cannot be read
            safely — it is then left out. pycocotools trusts what it is given, and masks a person
            wrote reach it: the caller checks them.
    """

    record_id: str
    entities: Sequence[Any]
    annotations: Mapping[str, Sequence[Any]]
    image_size: Callable[[str], tuple[int, int] | None]
    mask_grid: MaskReader


@dataclass
class ComputedValues:
    """The values of statistics for one record.

    Attributes:
        record: The value of each statistic per record, by column.
        entities: The value of each statistic per object, by object, then by column.
    """

    record: dict[str, StatisticValue] = field(default_factory=dict)
    entities: dict[str, dict[str, StatisticValue]] = field(default_factory=dict)


def compute_values(definitions: Sequence[StatisticDefinition], content: RecordContent) -> ComputedValues:
    """Compute statistics for a record and for each of its objects.

    Args:
        definitions: The statistics to compute.
        content: What the record holds.

    Returns:
        The value of each statistic per record, and of each statistic per object for every object of
        the record.
    """
    entities_by_id = {entity.id: entity for entity in content.entities}
    computed = ComputedValues(entities={entity.id: {} for entity in content.entities})
    for definition in definitions:
        choices = definition.choices
        if choices.level is StatisticLevel.RECORD:
            computed.record[definition.name] = _record_value(choices, content, entities_by_id)
            continue
        kept_by_entity: dict[str, list[Any]] = defaultdict(list)
        for annotation in _kept_annotations(choices, content, entities_by_id):
            kept_by_entity[annotation.entity_id].append(annotation)
        for entity in content.entities:
            if choices.attribute is not None and not _has_attribute(entity, choices):
                computed.entities[entity.id][definition.name] = None
                continue
            computed.entities[entity.id][definition.name] = _measure(choices, kept_by_entity[entity.id], content)
    return computed


def _record_value(choices: StatisticChoices, content: RecordContent, entities_by_id: dict[str, Any]) -> StatisticValue:
    """A statistic per record: its objects counted, or its annotations measured."""
    if choices.element == ENTITY_ELEMENT:
        # The objects a person sees on the record: those that are no part of another.
        objects = [entity for entity in content.entities if not entity.parent_id]
        if choices.attribute is not None:
            objects = [entity for entity in objects if _has_attribute(entity, choices)]
        return len(objects)
    return _measure(choices, _kept_annotations(choices, content, entities_by_id), content)


def _kept_annotations(choices: StatisticChoices, content: RecordContent, entities_by_id: dict[str, Any]) -> list[Any]:
    """The annotations of the element measured that the statistic's filters keep."""
    kept = []
    for annotation in content.annotations.get(choices.element, ()):
        is_a_models = annotation.source_type == _MODEL_SOURCE
        if choices.origin is AnnotationOrigin.MODEL and not is_a_models:
            continue
        if choices.origin is AnnotationOrigin.NOT_MODEL and is_a_models:
            continue
        if choices.review_status is not None and not (
            is_a_models and annotation.review_status in stored_statuses(choices.review_status)
        ):
            continue
        if choices.attribute is not None:
            entity = entities_by_id.get(annotation.entity_id)
            if entity is None or not _has_attribute(entity, choices):
                continue
        kept.append(annotation)
    return kept


def _has_attribute(entity: Any, choices: StatisticChoices) -> bool:
    """Whether an object has the attribute value a statistic filters on."""
    if choices.attribute is None:  # pragma: no cover - callers check
        return True
    value = getattr(entity, choices.attribute.field, None)
    if isinstance(value, bool):
        return ("true" if value else "false") == choices.attribute.value
    return value is not None and str(value) == choices.attribute.value


def _measure(choices: StatisticChoices, annotations: list[Any], content: RecordContent) -> StatisticValue:
    """Annotations counted, or their areas aggregated: those whose area is unknown left out."""
    if choices.measure is StatisticMeasure.COUNT:
        return len(annotations)
    measured = [_area_value(choices, annotation, content) for annotation in annotations]
    values = [value for value in measured if value is not None]
    return _aggregate(choices.aggregation, values, nothing_kept=not annotations)


def drawn_on(box: Any) -> str:
    """The view a box is drawn on: its frame when it names one — a box of a sequence names the
    sequence's first view —, else its view.
    """
    return getattr(box, "frame_id", "") or box.view_id


def _area_value(choices: StatisticChoices, annotation: Any, content: RecordContent) -> float | None:
    """An annotation's area in pixels, or the share of its image it covers; None when unknown.

    A value that is not a finite number of at least zero — a box with an infinite coordinate,
    which a box's validation lets through — is unknown too: no area is infinite, nor negative.
    """
    value = _raw_area_value(choices, annotation, content)
    return value if value is not None and math.isfinite(value) and value >= 0 else None


def _raw_area_value(choices: StatisticChoices, annotation: Any, content: RecordContent) -> float | None:
    """An annotation's area, or share, as its geometry gives it; None when a size is unknown."""
    if choices.element == MASK_ELEMENT:
        # Counted on the mask's own grid: a mask drawn on a resized copy of its image counts that
        # copy's pixels.
        grid = content.mask_grid(annotation)
        if grid is None:
            return None
        height, width, painted = grid
        if choices.measure is StatisticMeasure.AREA:
            return float(painted)
        return painted / (width * height) if width > 0 and height > 0 else None
    # A box: its area in pixels needs its image's size when its coordinates are normalized, its share
    # of the image when they are not. The size is asked for then only: it may mean opening the image.
    _, _, width, height = annotation.xywh_coords
    if choices.measure is StatisticMeasure.AREA and not annotation.is_normalized:
        return float(width * height)
    if choices.measure is StatisticMeasure.IMAGE_RATIO and annotation.is_normalized:
        return float(width * height)
    size = content.image_size(drawn_on(annotation))
    if size is None or size[0] <= 0 or size[1] <= 0:
        return None
    image_width, image_height = size
    if choices.measure is StatisticMeasure.AREA:
        return float(width * image_width * height * image_height)
    return float(width * height) / (image_width * image_height)


def _aggregate(aggregation: StatisticAggregation | None, values: list[float], nothing_kept: bool) -> float | None:
    """Several values as one. A sum of nothing kept is zero; any other aggregation of nothing is none."""
    if aggregation is StatisticAggregation.SUM:
        if values:
            return float(sum(values))
        return 0.0 if nothing_kept else None
    if not values:
        return None
    if aggregation is StatisticAggregation.MEAN:
        return fmean(values)
    if aggregation is StatisticAggregation.MIN:
        return min(values)
    if aggregation is StatisticAggregation.MAX:
        return max(values)
    raise ValueError(f"Unknown aggregation: {aggregation}.")  # pragma: no cover - `StatisticChoices` requires one
