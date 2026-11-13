# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A dataset's overview: how its records, media and annotations spread (backend-processing §22.7).

As Know Your Data shows a dataset: a card per thing measured, each a histogram of its values or the
count of each of them, read when asked over the records the explorer's filters keep, so that a
filter added from a card shows on every other card. A card whose own column is filtered counts the
records the other filters keep, and says how many of each bar its own filters keep: the bar clicked
stays among the others rather than alone.

- the records' own fields: a text or yes-or-no field by its values, a number by a histogram;
- the statistics the dataset computed per record (`DatasetInfo.statistics`), the default ones among
  them (`pixano.statistics.defaults`): how many objects, boxes and masks each record holds;
- its images: the width, height, aspect ratio and format their metadata give, and how many each
  record holds;
- its objects — those that are no part of another, as the number of objects counts them —: how
  many of each class, and the statistics computed per object — the share of its image an object's
  box covers.

Each card can count its values per split of their record, so that the splits compare as Facets
compares them. Nothing is read from the pixels.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

import duckdb
import pyarrow as pa
from pydantic import BaseModel, Field

from pixano.datasets.dataset_schema import serialize_all_fields
from pixano.datasets.queries.computed_columns import (
    COMPUTED_COLUMN_PREFIX,
    KEPT_BY_PREFIX,
    RECORD_STATISTICS_TABLE,
    CrossFilter,
    matching_records,
    quote_identifier,
    read_latest,
)
from pixano.datasets.statistic_choices import default_statistics_to_compute
from pixano.schemas import SchemaGroup, canonical_table_name_for_slot, label_field_of, media_type_of
from pixano.schemas.statistics import statistics_slot
from pixano.statistics.computed import ComputedStatistic
from pixano.statistics.definitions import StatisticDefinition, StatisticLevel
from pixano.statistics.registry import StatisticRegistry
from pixano.utils.python import quote_sql_string


if TYPE_CHECKING:
    from pixano.datasets import Dataset


logger = logging.getLogger(__name__)

#: The most bars a range of values is cut into.
BARS = 20
#: The most whole values a range can span and still get a bar per value: a bar per number of boxes,
#: up to forty.
MAX_VALUE_BARS = 40
#: The most values a card of values lists, by decreasing count; the others are counted together.
#: Enough to read a dataset's main classes, few enough for a card's width.
MAX_LISTED_VALUES = 20
#: The split of a record that names none, as the cards count it.
NO_SPLIT = ""

#: The records' fields an overview leaves out: an identifier and timestamps tell nothing of the data,
#: nor does the note an annotator writes on a record.
_SKIPPED_RECORD_FIELDS = frozenset({"id", "created_at", "updated_at", "comment"})
#: The types of the fields a card shows, by how: by their values, or by a histogram.
_VALUE_TYPES = frozenset({"str", "bool"})
_NUMBER_TYPES = frozenset({"int", "float"})

_RECORDS_TABLE = SchemaGroup.RECORD.value
_ENTITIES_TABLE = canonical_table_name_for_slot("entity")
_ENTITY_STATISTICS_TABLE = canonical_table_name_for_slot(statistics_slot(StatisticLevel.ENTITY.value))
_IMAGE_MEDIA = "image"

#: How the cards' queries name the records the filters of the columns without a card keep — those
#: of the columns with one told on each record —, and those every filter keeps.
_CANDIDATES = "candidates"
_KEPT = "kept"
#: How they name the column of each record's split, of the value a card counts, and whether the
#: filters of the card's own column keep its record.
_SPLIT = "split"
_VALUE = "value"
_SELECTED = "selected"

CardGroup = Literal["records", "media", "annotations"]
#: The order of the overview's parts.
_GROUP_ORDER: tuple[CardGroup, ...] = ("records", "media", "annotations")
CardSubject = Literal["record", "image", "object"]
CardKind = Literal["histogram", "values"]


class OverviewBar(BaseModel):
    """A bar of a histogram: the values from `start` to `end`.

    Attributes:
        start: The smallest value it counts.
        end: Of whole values, the value after the last it counts; of other numbers, the value it
            stops before, but for the last bar, which ends at the largest value and counts it.
        count: How many hold a value in it.
        selected: How many of them the filters of the card's own column keep, when it is filtered.
        by_split: Those per split of their record, when asked.
    """

    start: float
    end: float
    count: int
    selected: int | None = None
    by_split: dict[str, int] = Field(default_factory=dict)


class OverviewValue(BaseModel):
    """A value of a card of values, and how many hold it.

    Attributes:
        value: The value, as text; `true` or `false` for a yes-or-no field.
        count: How many hold it.
        selected: How many of them the filters of the card's own column keep, when it is filtered.
        by_split: Those per split of their record, when asked.
    """

    value: str
    count: int
    selected: int | None = None
    by_split: dict[str, int] = Field(default_factory=dict)


class OverviewCard(BaseModel):
    """What the overview shows of one thing measured: a histogram, or the count of each value.

    Attributes:
        id: What names the card from one reading to the next.
        group: The part of the overview it belongs to.
        label: What a person reads for it.
        unit: The unit of its values, if they have one.
        subject: What holds its values: a record, an image, an object.
        kind: A histogram of numbers, or the values counted.
        population: How many records, images or objects the filters keep — but those of its own
            column, when it is filtered (`filtered`).
        missing: Those without a value.
        counted_by_split: Those with a value, per split of their record, when asked: what a share of
            a split is counted out of.
        filter_column: The explorer's column a bar or a value filters the records on; none when the
            values are not the records' own — an image's, an object's.
        filtered: Whether the explorer filters the records on its column: it then counts those the
            other filters keep, and its bars and values say how many of them its own filters keep.
        computed_at: When the statistic it shows was computed, for a statistic's card: it does not
            follow the annotations edited since.
        whole_values: Whether its numbers are whole: a histogram's bars are then whole values.
        minimum: The smallest number.
        maximum: The largest number.
        mean: Their mean.
        median: Their median.
        bars: A histogram's bars, from the smallest values to the largest.
        values: The values counted, by decreasing count, at most `MAX_LISTED_VALUES`.
        distinct: How many different values there are.
        others: How many hold a value not listed.
        others_selected: How many of them the filters of its own column keep, when it is filtered.
        others_by_split: Those per split of their record, when asked.
    """

    id: str
    group: CardGroup
    label: str
    unit: str = ""
    subject: CardSubject
    kind: CardKind
    population: int
    missing: int
    counted_by_split: dict[str, int] = Field(default_factory=dict)
    filter_column: str | None = None
    filtered: bool = False
    computed_at: datetime | None = None
    whole_values: bool = False
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    bars: list[OverviewBar] = Field(default_factory=list)
    values: list[OverviewValue] = Field(default_factory=list)
    distinct: int = 0
    others: int = 0
    others_selected: int | None = None
    others_by_split: dict[str, int] = Field(default_factory=dict)


class DatasetOverview(BaseModel):
    """How a dataset's records, media and annotations spread, over the records the filters keep.

    Attributes:
        records: The records the filters keep.
        total_records: The records the dataset holds.
        splits: The splits of the records the request reads — those the free text, a raw clause and
            the filters of the columns without a card keep —, in alphabetical order, none named the
            last: a split keeps its place, and its color, from card to card.
        cards: The cards, records first, then media, then annotations.
        statistics_to_compute: The default statistics the dataset has no values of: its cards come
            once they are computed.
    """

    records: int
    total_records: int
    splits: list[str] = Field(default_factory=list)
    cards: list[OverviewCard] = Field(default_factory=list)
    statistics_to_compute: list[StatisticDefinition] = Field(default_factory=list)


@dataclass(frozen=True)
class _Card:
    """What a card is, before its values are counted.

    Attributes:
        id: What names it.
        group: The part of the overview it belongs to.
        label: What a person reads for it.
        subject: What holds its values.
        kind: A histogram of numbers, or the values counted.
        source: The query of its values: a row per record, image or object, with `_VALUE` — none where
            it holds no value —, `_SPLIT`, its record's split, and `_SELECTED`, whether the filters of
            its own column keep its record.
        unit: The unit of its values.
        filter_column: The explorer's column its values filter the records on, if they are theirs.
        filtered: Whether the explorer filters the records on that column.
        computed_at: When the statistic it shows was computed.
        whole_values: For a histogram, whether its numbers are whole.
    """

    id: str
    group: CardGroup
    label: str
    subject: CardSubject
    kind: CardKind
    source: str
    unit: str = ""
    filter_column: str | None = None
    filtered: bool = False
    computed_at: datetime | None = None
    whole_values: bool = False


@dataclass(frozen=True)
class _CountedOver:
    """The records a card of the records' own values counts.

    Attributes:
        relation: The query's name of them.
        selected: The column that says whether the filters of the card's column keep a record, when
            they are left out of the relation; none otherwise.
    """

    relation: str
    selected: str | None = None

    def selection(self) -> str:
        """What the card's query reads for `_SELECTED`."""
        return self.selected if self.selected is not None else "false"


def dataset_overview(
    dataset: Dataset,
    cross_filter: CrossFilter,
    by_split: bool = False,
    registry: StatisticRegistry | None = None,
) -> DatasetOverview:
    """The overview of the records a request on the explorer keeps.

    Args:
        dataset: The dataset.
        cross_filter: The request, its filters per column: a card of a column filtered counts the
            records the other filters keep.
        by_split: Whether each card also counts its values per split of their record.
        registry: The library's statistics, whose labels the statistics to compute keep.

    Returns:
        The overview.

    Raises:
        InvalidRecordFilter: LanceDB refused the request's condition on the records.
    """
    fields = _record_fields(dataset)
    record_statistics = _computed_statistics(dataset, StatisticLevel.RECORD, RECORD_STATISTICS_TABLE)
    carded = {name for name, _type in fields} | {
        _statistic_column(computed.definition) for computed in record_statistics
    }
    apart = [column for column in cross_filter.columns if column in carded]
    candidates = matching_records(
        dataset,
        cross_filter,
        record_columns=list(dict.fromkeys([_SPLIT, *(name for name, _type in fields)])),
        computed_columns=[computed.definition.name for computed in record_statistics],
        apart=apart,
    )
    with duckdb.connect() as connection:
        connection.register(_CANDIDATES, candidates)
        over = _kept_relations(connection, apart)
        every = _CountedOver(_KEPT)
        cards = [
            *[_field_card(name, field_type, over.get(name, every)) for name, field_type in fields],
            *[
                _record_statistic_card(computed, over.get(_statistic_column(computed.definition), every))
                for computed in record_statistics
            ],
            *_image_cards(connection, dataset),
            *_object_cards(connection, dataset),
        ]
        ordered = sorted(cards, key=lambda card: _GROUP_ORDER.index(card.group))
        counted = [_counted(connection, card, by_split) for card in ordered]
        (records,) = _one(connection, f"SELECT count(*) FROM {_KEPT}")
        splits = _splits(connection)
    return DatasetOverview(
        records=records,
        total_records=dataset.num_rows,
        splits=splits,
        cards=counted,
        statistics_to_compute=_statistics_to_compute(dataset, registry),
    )


def _statistics_to_compute(dataset: Dataset, registry: StatisticRegistry | None) -> list[StatisticDefinition]:
    """The default statistics the dataset has no values of; none, logged, when what tells them cannot be
    read — the library's registry, a table of annotations —: the overview does not fail for them.
    """
    try:
        return default_statistics_to_compute(dataset, registry)
    except Exception as error:  # noqa: BLE001 - an unreadable registry or table offers nothing to compute
        logger.warning("Dataset %s: its default statistics to compute cannot be told: %s", dataset.info.id, error)
        return []


def _kept_relations(connection: duckdb.DuckDBPyConnection, apart: list[str]) -> dict[str, _CountedOver]:
    """Name the records the cards count: those every filter keeps (`_KEPT`), and for each column whose
    filters are told, those every other column's filters keep.

    Returns:
        What a card of each column told counts over.
    """

    def kept_by_all_but(excluded: str | None) -> str:
        told = [quote_identifier(KEPT_BY_PREFIX + column) for column in apart if column != excluded]
        return " AND ".join(told) if told else "true"

    connection.execute(f"CREATE TEMP VIEW {_KEPT} AS SELECT * FROM {_CANDIDATES} WHERE {kept_by_all_but(None)}")
    over: dict[str, _CountedOver] = {}
    for index, column in enumerate(apart):
        relation = f"kept_without_{index}"
        connection.execute(
            f"CREATE TEMP VIEW {relation} AS SELECT * FROM {_CANDIDATES} WHERE {kept_by_all_but(column)}"
        )
        over[column] = _CountedOver(relation, quote_identifier(KEPT_BY_PREFIX + column))
    return over


def _record_fields(dataset: Dataset) -> list[tuple[str, str]]:
    """The records' fields a card shows, with their types: the base fields first, then the others by name."""
    schema = dataset.info.tables[_RECORDS_TABLE]
    physical = set(dataset.open_table(_RECORDS_TABLE).schema.names)
    base = {"split", "status"}
    fields = [
        (name, descriptor["type"])
        for name, descriptor in serialize_all_fields(schema).items()
        if name in physical
        and name not in _SKIPPED_RECORD_FIELDS
        and not descriptor.get("collection")
        and descriptor["type"] in _VALUE_TYPES | _NUMBER_TYPES
    ]
    return sorted(fields, key=lambda field: (field[0] not in base, field[0]))


def _computed_statistics(dataset: Dataset, level: StatisticLevel, table_name: str) -> list[ComputedStatistic]:
    """The statistics of a level the dataset computed and whose column its table holds, in the order
    they were computed.
    """
    computed = [statistic for statistic in dataset.info.statistics if statistic.definition.level is level]
    if not computed or table_name not in dataset.info.tables:
        return []
    try:
        held = set(dataset.open_latest_table(table_name).schema.names)
    except Exception:  # noqa: BLE001 - a broken table shows no card, it fails no overview
        return []
    return [statistic for statistic in computed if statistic.definition.name in held]


def _statistic_column(definition: StatisticDefinition) -> str:
    """The explorer's column of a statistic computed per record."""
    return f"{RECORD_STATISTICS_TABLE}.{definition.name}"


def _field_card(name: str, field_type: str, over: _CountedOver) -> _Card:
    """The card of a record's field: its values, or a histogram of its numbers."""
    value = quote_identifier(name)
    if field_type == "bool":
        held = f"CAST({value} AS VARCHAR)"
    elif field_type == "str":
        held = f"NULLIF({value}, '')"
    else:
        held = value
    return _Card(
        id=f"field:{name}",
        group="records",
        label=_field_label(name),
        subject="record",
        kind="histogram" if field_type in _NUMBER_TYPES else "values",
        source=f"SELECT {held} AS {_VALUE}, {_SPLIT}, {over.selection()} AS {_SELECTED} FROM {over.relation}",
        filter_column=name,
        filtered=over.selected is not None,
        whole_values=field_type == "int",
    )


def _field_label(name: str) -> str:
    """A field's name as a person reads it: `num_objects` gives "Num objects"."""
    words = name.strip("_").replace("_", " ")
    return words[:1].upper() + words[1:]


def _record_statistic_card(computed: ComputedStatistic, over: _CountedOver) -> _Card:
    """The card of a statistic computed per record: a histogram of its values."""
    definition = computed.definition
    value = quote_identifier(COMPUTED_COLUMN_PREFIX + definition.name)
    return _Card(
        id=f"statistic:{definition.name}",
        group="annotations",
        label=definition.label,
        subject="record",
        kind="histogram",
        source=f"SELECT {value} AS {_VALUE}, {_SPLIT}, {over.selection()} AS {_SELECTED} FROM {over.relation}",
        unit=definition.unit,
        filter_column=_statistic_column(definition),
        filtered=over.selected is not None,
        computed_at=computed.computed_at,
        whole_values=definition.value_type == "int",
    )


def _image_cards(connection: duckdb.DuckDBPyConnection, dataset: Dataset) -> list[_Card]:
    """The cards of the images: their width, height, aspect ratio and format, and how many a record holds.

    A size of zero is the one an image's metadata did not give.
    """
    tables = [name for name, schema in dataset.info.tables.items() if media_type_of(schema) == _IMAGE_MEDIA]
    cards: list[_Card] = []
    for table_name in tables:
        rows = _read(dataset, table_name, ["record_id", "width", "height", "format"])
        if rows is None:
            continue
        images = f"images_{len(cards)}"
        connection.register(images, rows)
        named = f" ({table_name})" if len(tables) > 1 else ""
        joined = f"FROM {images} i JOIN {_KEPT} k ON k.id = i.record_id"
        unselected = f"false AS {_SELECTED}"
        cards += [
            _Card(
                id=f"image:{table_name}:width",
                group="media",
                kind="histogram",
                label=f"Image width{named}",
                subject="image",
                source=f"SELECT NULLIF(i.width, 0) AS {_VALUE}, k.{_SPLIT}, {unselected} {joined}",
                unit="px",
                whole_values=True,
            ),
            _Card(
                id=f"image:{table_name}:height",
                group="media",
                kind="histogram",
                label=f"Image height{named}",
                subject="image",
                source=f"SELECT NULLIF(i.height, 0) AS {_VALUE}, k.{_SPLIT}, {unselected} {joined}",
                unit="px",
                whole_values=True,
            ),
            _Card(
                id=f"image:{table_name}:aspect_ratio",
                group="media",
                kind="histogram",
                label=f"Aspect ratio, width to height{named}",
                subject="image",
                source=(
                    f"SELECT CASE WHEN i.width > 0 AND i.height > 0 THEN i.width::DOUBLE / i.height END "
                    f"AS {_VALUE}, k.{_SPLIT}, {unselected} {joined}"
                ),
            ),
            _Card(
                id=f"image:{table_name}:format",
                group="media",
                kind="values",
                label=f"Image format{named}",
                subject="image",
                source=f"SELECT NULLIF(lower(i.format), '') AS {_VALUE}, k.{_SPLIT}, {unselected} {joined}",
            ),
            _Card(
                id=f"image:{table_name}:per_record",
                group="media",
                kind="histogram",
                label=f"Images per record{named}",
                subject="record",
                source=(
                    f"SELECT count(i.record_id) AS {_VALUE}, k.{_SPLIT}, {unselected} FROM {_KEPT} k "
                    f"LEFT JOIN {images} i ON i.record_id = k.id GROUP BY k.id, k.{_SPLIT}"
                ),
                whole_values=True,
            ),
        ]
    return cards


def _object_cards(connection: duckdb.DuckDBPyConnection, dataset: Dataset) -> list[_Card]:
    """The cards of the objects: how many of each class, and the statistics computed per object.

    An object is one that is no part of another, as the number of objects per record counts them, and
    every such object counts: one created since the statistics were computed counts as without a
    value of them, and the values of an object deleted since are not read.
    """
    schema = dataset.info.tables.get(_ENTITIES_TABLE)
    if schema is None:
        return []
    label = label_field_of(schema)
    rows = _read(dataset, _ENTITIES_TABLE, ["id", "record_id"], optional=["parent_id", *([label] if label else [])])
    if rows is None:
        return []
    connection.register("objects", rows)
    objects = f"FROM objects o JOIN {_KEPT} k ON k.id = o.record_id"
    top_level = "WHERE coalesce(o.parent_id, '') = ''"
    unselected = f"false AS {_SELECTED}"
    cards: list[_Card] = []
    if label is not None:
        cards.append(
            _Card(
                id="object:class",
                group="annotations",
                kind="values",
                label="Objects per class",
                subject="object",
                source=(
                    f"SELECT NULLIF(o.{quote_identifier(label)}, '') AS {_VALUE}, k.{_SPLIT}, {unselected} "
                    f"{objects} {top_level}"
                ),
            )
        )
    statistics = _computed_statistics(dataset, StatisticLevel.ENTITY, _ENTITY_STATISTICS_TABLE)
    names = [computed.definition.name for computed in statistics]
    measured = (
        read_latest(dataset, _ENTITY_STATISTICS_TABLE, ["entity_id", *names], None, required=["entity_id"])
        if statistics
        else None
    )
    if measured is None:
        return cards
    connection.register("object_statistics", measured)
    # An object has one row of statistics: should two be stored, one is read, as for the records'.
    joined = (
        "LEFT JOIN (SELECT * FROM object_statistics QUALIFY row_number() OVER (PARTITION BY entity_id) = 1) s "
        "ON s.entity_id = o.id"
    )
    for computed in statistics:
        definition = computed.definition
        if definition.name not in measured.schema.names:
            continue
        cards.append(
            _Card(
                id=f"object_statistic:{definition.name}",
                group="annotations",
                kind="histogram",
                label=definition.label,
                subject="object",
                source=(
                    f"SELECT s.{quote_identifier(definition.name)} AS {_VALUE}, k.{_SPLIT}, {unselected} "
                    f"{objects} {joined} {top_level}"
                ),
                unit=definition.unit,
                computed_at=computed.computed_at,
                whole_values=definition.value_type == "int",
            )
        )
    return cards


def _read(dataset: Dataset, table_name: str, columns: list[str], optional: Sequence[str] = ()) -> pa.Table | None:
    """These columns of every row of a table, and the optional ones it holds, those it lacks read as
    texts without a value; None when it lacks one of the others or cannot be read — its cards are left
    out, the overview does not fail.
    """
    try:
        table = dataset.open_table(table_name)
        held = table.schema.names
        if any(column not in held for column in columns):
            return None
        present = [*columns, *(column for column in optional if column in held)]
        # LanceDB applies its default limit of ten rows unless told otherwise; a limit of zero is refused.
        rows = table.search(None).select(present).limit(max(table.count_rows(), 1)).to_arrow()
    except Exception:  # noqa: BLE001 - an unreadable table shows no card, it fails no overview
        return None
    for column in optional:
        if column not in rows.schema.names:
            rows = rows.append_column(column, pa.nulls(rows.num_rows, pa.string()))
    return rows


def _one(connection: duckdb.DuckDBPyConnection, query: str) -> tuple[Any, ...]:
    """The one row an aggregate answers."""
    row = connection.execute(query).fetchone()
    if row is None:  # pragma: no cover - an aggregate answers a row
        raise RuntimeError(f"No row answered: {query}")
    return tuple(row)


def _splits(connection: duckdb.DuckDBPyConnection) -> list[str]:
    """The splits of the records the request reads, in alphabetical order, none named the last."""
    rows = connection.execute(f"SELECT DISTINCT coalesce({_SPLIT}, ?) FROM {_CANDIDATES}", [NO_SPLIT]).fetchall()
    return sorted((row[0] for row in rows), key=lambda split: (split == NO_SPLIT, split))


def _counted(connection: duckdb.DuckDBPyConnection, card: _Card, by_split: bool) -> OverviewCard:
    """A card, its values counted: a histogram of numbers, or a count of each value.

    A number that is not finite counts as no value, as does an empty text. The card's values are read
    once, into a table its counts read.
    """
    held = (
        f"CASE WHEN isfinite({_VALUE}::DOUBLE) THEN {_VALUE}::DOUBLE END"
        if card.kind == "histogram"
        else f"CAST({_VALUE} AS VARCHAR)"
    )
    # A statement creating a table takes no parameter: the split of a record naming none is written in it.
    connection.execute(
        f"CREATE OR REPLACE TEMP TABLE card_values AS SELECT {held} AS {_VALUE}, "
        f"coalesce({_SPLIT}, {quote_sql_string(NO_SPLIT)}) AS {_SPLIT}, {_SELECTED} FROM ({card.source})"
    )
    common: dict[str, Any] = {
        "id": card.id,
        "group": card.group,
        "label": card.label,
        "unit": card.unit,
        "subject": card.subject,
        "kind": card.kind,
        "filter_column": card.filter_column,
        "filtered": card.filtered,
        "computed_at": card.computed_at,
    }
    population, counted = _one(connection, f"SELECT count(*), count({_VALUE}) FROM card_values")
    common.update(population=population, missing=population - counted)
    if by_split:
        common["counted_by_split"] = _counted_by_split(connection)
    if card.kind == "values":
        values = _value_counts(connection, counted, common.get("counted_by_split"), card.filtered)
        return OverviewCard(**common, **values)
    histogram = _histogram(connection, card.whole_values, by_split, card.filtered)
    return OverviewCard(whole_values=card.whole_values, **common, **histogram)


def _value_counts(
    connection: duckdb.DuckDBPyConnection, counted: int, counted_by_split: dict[str, int] | None, filtered: bool
) -> dict[str, Any]:
    """The count of each value, the most held first, at most `MAX_LISTED_VALUES` of them, and of the others."""
    (distinct,) = _one(connection, f"SELECT count(DISTINCT {_VALUE}) FROM card_values")
    listed = connection.execute(
        f"SELECT {_VALUE}, count(*) AS n, count(*) FILTER (WHERE {_SELECTED}) FROM card_values "
        f"WHERE {_VALUE} IS NOT NULL GROUP BY 1 ORDER BY n DESC, 1 LIMIT ?",
        [MAX_LISTED_VALUES],
    ).fetchall()
    values = [
        OverviewValue(value=value, count=count, selected=selected if filtered else None)
        for value, count, selected in listed
    ]
    result: dict[str, Any] = {
        "values": values,
        "distinct": distinct,
        "others": counted - sum(value.count for value in values),
    }
    if filtered:
        (selected,) = _one(
            connection, f"SELECT count(*) FILTER (WHERE {_SELECTED}) FROM card_values WHERE {_VALUE} IS NOT NULL"
        )
        result["others_selected"] = selected - sum(value.selected or 0 for value in values)
    if counted_by_split is not None:
        per_split = _per_split(connection, [value.value for value in values])
        listed_by_split: dict[str, int] = {}
        for value in values:
            value.by_split = per_split.get(value.value, {})
            for split, count in value.by_split.items():
                listed_by_split[split] = listed_by_split.get(split, 0) + count
        result["others_by_split"] = {
            split: count - listed_by_split.get(split, 0)
            for split, count in counted_by_split.items()
            if count > listed_by_split.get(split, 0)
        }
    return result


def _histogram(connection: duckdb.DuckDBPyConnection, whole: bool, by_split: bool, filtered: bool) -> dict[str, Any]:
    """The histogram of a card's numbers, with their smallest, largest, mean and median."""
    minimum, maximum, mean, median = _one(
        connection,
        f"SELECT min({_VALUE}), max({_VALUE}), avg({_VALUE}), quantile_cont({_VALUE}, 0.5) FROM card_values",
    )
    if minimum is None:
        return {}
    start, width, count = _bars_of(minimum, maximum, whole)
    starts = [start + bar * width for bar in range(count)]
    # A value is counted in the last bar whose start, as it is sent, is at most the value: the very
    # comparison the bar's filter makes. Dividing by the width instead puts a value on an edge, 0.85
    # among bars of 0.05 from 0, in the bar before the one whose filter keeps it.
    index = f"greatest(0, len(list_filter(?, lambda bar_start: bar_start <= {_VALUE})) - 1)::INTEGER"
    counts = [0] * count
    selected = [0] * count
    splits: list[dict[str, int]] = [{} for _ in range(count)]
    rows = connection.execute(
        f"SELECT {index}, {_SPLIT}, count(*), count(*) FILTER (WHERE {_SELECTED}) FROM card_values "
        f"WHERE {_VALUE} IS NOT NULL GROUP BY 1, 2",
        [starts],
    ).fetchall()
    for bar, split, held, kept in rows:
        counts[bar] += held
        selected[bar] += kept
        if by_split:
            splits[bar][split] = held
    return {
        "minimum": minimum,
        "maximum": maximum,
        "mean": mean,
        "median": median,
        "bars": [
            OverviewBar(
                start=starts[bar],
                end=_bar_end(start, width, bar, count, maximum, whole),
                count=counts[bar],
                selected=selected[bar] if filtered else None,
                by_split=splits[bar],
            )
            for bar in range(count)
        ],
    }


def _bars_of(minimum: float, maximum: float, whole: bool) -> tuple[float, float, int]:
    """Where the bars start, how wide each is, and how many there are.

    Whole numbers spanning at most `MAX_VALUE_BARS` values get a bar each; any other range is cut into
    at most `BARS` bars of equal width — whole ones for whole numbers, so that a span of forty-one
    values gets fourteen bars of three.
    """
    if whole:
        span = int(maximum - minimum) + 1
        width = 1 if span <= MAX_VALUE_BARS else math.ceil(span / BARS)
        return minimum, width, math.ceil(span / width)
    if maximum == minimum:
        return minimum, 0, 1
    return minimum, (maximum - minimum) / BARS, BARS


def _bar_end(start: float, width: float, bar: int, count: int, maximum: float, whole: bool) -> float:
    """Where a bar ends: the last one at the largest value — just after it, for whole values."""
    if whole:
        return min(start + (bar + 1) * width, maximum + 1)
    return maximum if bar == count - 1 else start + (bar + 1) * width


def _per_split(connection: duckdb.DuckDBPyConnection, values: list[str]) -> dict[str, dict[str, int]]:
    """How many hold each of these values, per split: the values listed, not every one held."""
    per_split: dict[str, dict[str, int]] = {}
    rows = connection.execute(
        f"SELECT {_VALUE}, {_SPLIT}, count(*) FROM card_values WHERE list_contains(?, {_VALUE}) GROUP BY 1, 2",
        [values],
    ).fetchall()
    for held, split, count in rows:
        per_split.setdefault(held, {})[split] = count
    return per_split


def _counted_by_split(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """How many hold a value, per split: what a split's share of a value is counted out of."""
    rows = connection.execute(
        f"SELECT {_SPLIT}, count({_VALUE}) FROM card_values GROUP BY 1 HAVING count({_VALUE}) > 0"
    ).fetchall()
    return dict(rows)
