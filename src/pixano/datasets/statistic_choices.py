# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a dataset offers to compose a statistic from, and which statistics apply to it.

The choices come from the dataset, never from a fixed list: a dataset of masks offers no box, a
dataset whose objects have no class offers no class to filter on. A statistic of the library
applies to a dataset that holds what it measures and what it filters on (backend-processing §22),
and so do the default statistics every dataset gets for its overview (§22.7).

Both read the dataset's tables and their schemas (`info.tables`) and nothing else, so that the
worker, which sees a dataset through its reader, can decide as the application does.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pyarrow.compute as pc
from pydantic import BaseModel
from s3path import S3Path

from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_schema import serialize_all_fields
from pixano.schemas import Entity, ReviewStatus, canonical_table_name_for_slot
from pixano.statistics.defaults import DEFAULT_STATISTIC_CHOICES
from pixano.statistics.definitions import (
    ELEMENT_NAMES,
    ELEMENTS_WITH_AREA,
    ENTITY_ELEMENT,
    AnnotationOrigin,
    StatisticChoices,
    StatisticDefinition,
    StatisticLevel,
    StatisticMeasure,
    define_statistic,
    is_reviewable_element,
)
from pixano.statistics.registry import StatisticRegistry


#: The attribute types a statistic can filter objects on, with the values a yes-or-no field takes.
_TEXT_TYPE = "str"
_BOOL_TYPE = "bool"
_BOOL_VALUES = ("true", "false")

#: The most values an attribute lists, in alphabetical order. Enough for the largest vocabularies in
#: use (LVIS has 1203 categories); a field of more — an identifier, a comment — lists its first
#: values and says the list is not complete. A statistic can still filter on a value left out.
MAX_ATTRIBUTE_VALUES = 2000

#: The objects read at once to list an attribute's values: the memory a read takes is bounded by
#: them, and by the values kept, whatever the size of the dataset.
_VALUES_BATCH_SIZE = 50_000

_ENTITY_BASE_FIELDS = frozenset(Entity.model_fields)
_ENTITIES_TABLE = canonical_table_name_for_slot(ENTITY_ELEMENT)

#: Which dataset — its identifier, when it was made, its folder — at which version of its objects'
#: table: a dataset made again under the same identifier counts its tables' versions from the start,
#: and a file system may give its new folder the old one's inode, but not its creation date.
_CacheKey = tuple[str, str, tuple[int, int] | None, int]

# The values of each dataset's text attributes: a table written since is read again.
_values_cache: dict[_CacheKey, dict[str, tuple[list[str], bool]]] = {}


def _forget_values(dataset_id: str) -> None:
    """Drop the values cached for a dataset: it changed on disk, an import or a deletion."""
    for key in [key for key in list(_values_cache) if key[0] == dataset_id]:
        _values_cache.pop(key, None)


Dataset.register_cache_invalidation_hook(_forget_values)


class ElementChoice(BaseModel):
    """Something of the dataset a statistic can measure.

    Attributes:
        element: The annotation kind's `DatasetInfo` slot, or `entity` for the objects.
        name: What a person reads for it.
        levels: The levels it can be measured at.
        measures: How it can be measured.
        reviewable: Whether a model's annotations of it can be counted at a review status.
    """

    element: str
    name: str
    levels: list[StatisticLevel]
    measures: list[StatisticMeasure]
    reviewable: bool


class AttributeChoice(BaseModel):
    """An attribute of the dataset's objects a statistic can filter on.

    Attributes:
        field: The field.
        type: Its type, `str` or `bool`.
        values: The values it takes in the dataset, in alphabetical order.
        values_complete: False when the field takes more values than are listed.
    """

    field: str
    type: str
    values: list[str]
    values_complete: bool


class DatasetStatisticChoices(BaseModel):
    """Everything a dataset offers to compose a statistic from.

    Attributes:
        elements: What can be measured.
        attributes: What objects can be filtered on.
        origins: Whose annotations can be counted apart.
        review_statuses: The review statuses a model's annotations can be counted at.
    """

    elements: list[ElementChoice]
    attributes: list[AttributeChoice]
    origins: list[AnnotationOrigin]
    review_statuses: list[ReviewStatus]


def choices_for(dataset: Dataset) -> DatasetStatisticChoices:
    """What this dataset offers to compose a statistic from.

    Args:
        dataset: The dataset.

    Returns:
        Its elements, the attributes of its objects with their values, and the filters on origin
        and review status.
    """
    tables = dataset.info.tables
    has_objects = _ENTITIES_TABLE in tables
    elements = []
    for element, name in ELEMENT_NAMES.items():
        if not _holds(tables, element):
            continue
        if element == ENTITY_ELEMENT or not has_objects:
            levels = [StatisticLevel.RECORD]
        else:
            levels = [StatisticLevel.RECORD, StatisticLevel.ENTITY]
        measures = [StatisticMeasure.COUNT]
        if element in ELEMENTS_WITH_AREA:
            measures += [StatisticMeasure.AREA, StatisticMeasure.IMAGE_RATIO]
        elements.append(
            ElementChoice(
                element=element,
                name=name,
                levels=levels,
                measures=measures,
                reviewable=is_reviewable_element(element),
            )
        )
    return DatasetStatisticChoices(
        elements=elements,
        attributes=_attribute_choices(dataset),
        origins=list(AnnotationOrigin),
        review_statuses=list(ReviewStatus),
    )


def statistic_applies(choices: StatisticChoices, dataset: Any) -> bool:
    """Whether a statistic can be computed on this dataset.

    Args:
        choices: What the statistic is composed of.
        dataset: The dataset, or what reads it: anything whose `info.tables` holds its tables and their
            schemas.

    Returns:
        True when the dataset holds the element measured, objects for a statistic per object, and the
        attribute filtered on with a value of its type.
    """
    tables = dataset.info.tables
    if not _holds(tables, choices.element):
        return False
    if choices.level is StatisticLevel.ENTITY and _ENTITIES_TABLE not in tables:
        return False
    if choices.attribute is None:
        return True
    field_type = _attribute_types(tables).get(choices.attribute.field)
    if field_type is None:
        return False
    return field_type == _TEXT_TYPE or choices.attribute.value in _BOOL_VALUES


def default_statistics(dataset: Dataset, registry: StatisticRegistry | None = None) -> list[StatisticDefinition]:
    """The default statistics of this dataset, in the order the overview shows them.

    A default statistic is a dataset's when it applies to it (`statistic_applies`) and the table of
    what it counts holds a row: an import of images alone declares a table of objects and one of
    boxes, both empty, and there is nothing to count yet. Unlike `statistic_applies`, this reads the
    tables' rows, not only their schemas: the application's own rule, never the worker's.

    Each is the statistic as the dataset or its library holds it when either composed the same
    choices, so that the label a person gave it stays — the dataset's first, whose column the explorer
    names with it; otherwise the default composition.

    Args:
        dataset: The dataset.
        registry: The library's statistics; None to read the dataset's alone.

    Returns:
        The default statistics of the dataset.
    """
    held = [computed.definition for computed in dataset.info.statistics if computed.definition.is_current]
    composed = registry.definitions() if registry is not None else []
    statistics: list[StatisticDefinition] = []
    for choices in DEFAULT_STATISTIC_CHOICES:
        if not statistic_applies(choices, dataset) or not _holds_rows(dataset, choices.element):
            continue
        as_held: StatisticDefinition | None = next((d for d in held if d.choices == choices), None)
        as_composed: StatisticDefinition | None = next(
            (d for d in composed if d.choices == choices and d.is_current), None
        )
        statistics.append(as_held or as_composed or define_statistic(choices))
    return statistics


def default_statistics_to_compute(
    dataset: Dataset, registry: StatisticRegistry | None = None
) -> list[StatisticDefinition]:
    """The default statistics of this dataset whose values it does not hold.

    A statistic whose measure is computed otherwise since its values were is to compute again: its
    values are those of the previous computation.

    Args:
        dataset: The dataset.
        registry: The library's statistics, whose labels the statistics keep (`default_statistics`).

    Returns:
        The default statistics to compute, in the order the overview shows them.
    """
    held = [computed.definition.choices for computed in dataset.info.statistics if computed.definition.is_current]
    return [statistic for statistic in default_statistics(dataset, registry) if statistic.choices not in held]


def _holds_rows(dataset: Dataset, element: str) -> bool:
    """Whether the dataset's table of an element — its objects, or an annotation kind — holds a row."""
    table_name = canonical_table_name_for_slot(element)
    return table_name in dataset.info.tables and dataset.open_table(table_name).count_rows() > 0


def _holds(tables: Mapping[str, Any], element: str) -> bool:
    """Whether the dataset holds the objects, or the annotation kind, a statistic measures."""
    return canonical_table_name_for_slot(element) in tables


def _attribute_types(tables: Mapping[str, Any]) -> dict[str, str]:
    """The fields of the dataset's objects a statistic can filter on, with their types."""
    schema = tables.get(_ENTITIES_TABLE)
    if schema is None:
        return {}
    return {
        name: descriptor["type"]
        for name, descriptor in serialize_all_fields(schema).items()
        if name not in _ENTITY_BASE_FIELDS
        and not descriptor.get("collection")
        and descriptor["type"] in {_TEXT_TYPE, _BOOL_TYPE}
    }


def _attribute_choices(dataset: Dataset) -> list[AttributeChoice]:
    field_types = _attribute_types(dataset.info.tables)
    text_values = _text_values(dataset, [field for field, kind in field_types.items() if kind == _TEXT_TYPE])
    choices = []
    for field, field_type in sorted(field_types.items()):
        values, complete = (list(_BOOL_VALUES), True) if field_type == _BOOL_TYPE else text_values[field]
        choices.append(AttributeChoice(field=field, type=field_type, values=values, values_complete=complete))
    return choices


def _text_values(dataset: Dataset, fields: list[str]) -> dict[str, tuple[list[str], bool]]:
    """The distinct values of the objects' text fields: the first `MAX_ATTRIBUTE_VALUES` of each, in
    alphabetical order, and whether there are no more.

    One read of the objects' table for every field, batch by batch, keeping no more values per
    field than it lists and one more; cached until the table is written again.
    """
    if not fields:
        return {}
    table = dataset.open_table(_ENTITIES_TABLE)
    key: _CacheKey = (dataset.info.id, dataset.info.creation_date, _folder_identity(dataset), int(table.version))
    cached = _values_cache.get(key)
    if cached is not None and all(field in cached for field in fields):
        return {field: cached[field] for field in fields}

    present = [field for field in fields if field in table.schema.names]
    kept: dict[str, set[str]] = {field: set() for field in present}
    row_count = table.count_rows()
    if present and row_count:
        for batch in table.search(None).select(present).limit(row_count).to_batches(_VALUES_BATCH_SIZE):
            for field in present:
                seen = kept[field]
                seen.update(value for value in pc.unique(batch.column(field)).to_pylist() if value)
                if len(seen) > MAX_ATTRIBUTE_VALUES + 1:
                    # One more than listed says that the list is not complete.
                    kept[field] = set(sorted(seen)[: MAX_ATTRIBUTE_VALUES + 1])
    values: dict[str, tuple[list[str], bool]] = {}
    for field in fields:
        distinct = sorted(kept.get(field, ()))
        values[field] = (distinct[:MAX_ATTRIBUTE_VALUES], len(distinct) <= MAX_ATTRIBUTE_VALUES)
    for stale in [other for other in list(_values_cache) if other[0] == key[0] and other != key]:
        _values_cache.pop(stale, None)
    _values_cache[key] = {**(cached or {}), **values}
    return values


def _folder_identity(dataset: Dataset) -> tuple[int, int] | None:
    """The device and inode of the dataset's local folder; None on S3, whose folders have none."""
    if isinstance(dataset.path, S3Path):
        return None
    stat = dataset.path.stat()
    return (stat.st_dev, stat.st_ino)
