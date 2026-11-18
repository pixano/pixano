# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Records ordered and filtered through the columns computed from them (backend-processing §22.5).

The explorer sorts and filters records on columns a job computed from them, which live in tables of
their own: their statistics, in `record_statistics`, keyed by record. DuckDB joins them to the
records: LanceDB reads the identifiers of the records matching their own conditions, and the record
column sorted on if any; the computed tables give the columns a condition or the order reads. The
join orders and counts the records; the page's records are then read by their identifiers.

A computed table is read through a handle of its own at each call, never one a `Dataset` keeps:
another process may write and compact it meanwhile, and the files of the version a kept handle
stands on may be gone.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import duckdb
import pyarrow as pa

from pixano.schemas import SchemaGroup, canonical_table_name_for_slot
from pixano.utils.python import IDS_PER_QUERY, to_sql_list


if TYPE_CHECKING:
    from pixano.datasets import Dataset


logger = logging.getLogger(__name__)

#: The table of the records' statistics.
RECORD_STATISTICS_TABLE = canonical_table_name_for_slot("record_statistics")

#: How the join names the records, and the columns computed from them: a condition on a computed
#: column names it `c."column"` (`computed_sql_column`).
RECORDS_ALIAS = "r"
COMPUTED_ALIAS = "c"

#: What names a computed column among the columns of `matching_records`: apart from a record's own
#: column of the same name.
COMPUTED_COLUMN_PREFIX = "computed:"
#: What names, among the columns of `matching_records`, whether the filters of a column kept apart
#: keep a record.
KEPT_BY_PREFIX = "kept_by:"

_RECORDS_TABLE = SchemaGroup.RECORD.value

#: How many times a computed table is read before it counts as unreadable: once again, after a
#: compaction took the files of the version first read away.
_READ_ATTEMPTS = 2


class InvalidRecordFilter(ValueError):
    """LanceDB refused the condition on the records: a deprecated raw clause it could not read."""


@dataclass(frozen=True)
class ComputedFilter:
    """A condition on the columns computed from the records.

    Attributes:
        sql: The condition, in DuckDB's SQL, on the computed columns as `computed_sql_column` names
            them.
        columns: The computed columns it reads.
    """

    sql: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class RecordOrder:
    """How records are ordered: on one of their columns, or on a column computed from them.

    Attributes:
        column: The column: a record's, or a computed one.
        descending: Whether the largest value comes first.
        on_computed: Whether the column is a computed one.
    """

    column: str
    descending: bool
    on_computed: bool

    @property
    def direction(self) -> str:
        """``asc`` or ``desc``, as a sort is asked for."""
        return "desc" if self.descending else "asc"


#: Records in the order of their identifiers: what reading them with no other order means.
BY_ID = RecordOrder(column="id", descending=False, on_computed=False)


@dataclass(frozen=True)
class CrossFilter:
    """A request on the records, its filters kept apart per column, so that each column's can be left
    out in turn: a card of the overview counts the records the other columns' filters keep (§22.7).

    Attributes:
        where: The condition every record meets whatever the column — the free text, a raw clause —,
            as LanceDB reads it; None for none.
        on_records: Per record column filtered, the condition its filters make, as LanceDB reads it.
        on_computed: Per computed column filtered, the condition its filters make, as the join reads
            it. A column is named as the explorer names it, in both.
    """

    where: str | None = None
    on_records: Mapping[str, str] = field(default_factory=dict)
    on_computed: Mapping[str, ComputedFilter] = field(default_factory=dict)

    @property
    def columns(self) -> list[str]:
        """The columns filtered, the records' first."""
        return [*self.on_records, *self.on_computed]


def quote_identifier(name: str) -> str:
    """A column's name as SQL reads it whatever it holds: between double quotes, those doubled."""
    return '"' + name.replace('"', '""') + '"'


def computed_sql_column(name: str) -> str:
    """How a condition of the join names a computed column."""
    return f"{COMPUTED_ALIAS}.{quote_identifier(name)}"


def ordered_record_ids(
    dataset: Dataset,
    where: str | None,
    computed_filter: ComputedFilter | None,
    order: RecordOrder,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[str], int]:
    """The records matching both conditions, in order: a page of their identifiers, and their number.

    A record without a value in the computed column sorted on — none computed for it, or a value that
    is none — comes last, whatever the direction. Records equal on the column sorted on keep the order
    of their identifiers, so that pages do not overlap.

    Args:
        dataset: The dataset.
        where: A condition on the records' columns, as LanceDB reads it; None for every record.
        computed_filter: A condition on their computed columns; None for none.
        order: How to order them.
        limit: The page's size; None for every record matching.
        offset: How many records the page skips.

    Returns:
        The page's record identifiers, in order, and how many records match both conditions.

    Raises:
        InvalidRecordFilter: LanceDB refused `where`.
    """
    record_rows, computed_rows = _rows(dataset, where, computed_filter, order)
    with duckdb.connect() as connection:
        joined = _joined(connection, record_rows, computed_rows, computed_filter)
        page = f"SELECT {RECORDS_ALIAS}.id {joined} ORDER BY {_order_by(order)}"
        if limit is not None:
            page += f" LIMIT {int(limit)}"
        if offset:
            page += f" OFFSET {int(offset)}"
        ids = [row[0] for row in connection.execute(page).fetchall()]
        if computed_filter is None:
            # Joined with no condition, every record stays once: the records read are the total.
            return ids, record_rows.num_rows
        total_row = connection.execute(f"SELECT COUNT(*) {joined}").fetchone()
    return ids, int(total_row[0]) if total_row is not None else 0


def record_neighbors(
    dataset: Dataset,
    where: str | None,
    computed_filter: ComputedFilter | None,
    order: RecordOrder,
    record_id: str,
) -> dict[str, Any]:
    """Where a record stands among the records matching both conditions, in order.

    Without sorting them all: the records before it in the order are counted, the last of them is
    its previous and the first after it its next — a sort of every record took twice as long on a
    million of them.

    Args:
        dataset: The dataset.
        where: A condition on the records' columns, as LanceDB reads it; None for every record.
        computed_filter: A condition on their computed columns; None for none.
        order: How they are ordered.
        record_id: The record to locate.

    Returns:
        ``{"prev", "next", "position", "total"}``: its previous and next records, its 1-based
        position, and how many records match; a record that does not match has no previous, next
        nor position.

    Raises:
        InvalidRecordFilter: LanceDB refused `where`.
    """
    record_rows, computed_rows = _rows(dataset, where, computed_filter, order)
    alias = COMPUTED_ALIAS if order.on_computed else RECORDS_ALIAS
    # Before the record in the order: a value, where it has none; a value further in the
    # direction; or the same value — none included — and a smaller identifier.
    further = "<" if order.direction == "asc" else ">"
    before = (
        "((t.v IS NULL AND (o.v IS NOT NULL OR o.id < t.id)) "
        f"OR (t.v IS NOT NULL AND o.v IS NOT NULL AND (o.v {further} t.v OR (o.v = t.v AND o.id < t.id))))"
    )
    backwards = "desc" if order.direction == "asc" else "asc"
    with duckdb.connect() as connection:
        joined = _joined(connection, record_rows, computed_rows, computed_filter)
        located = connection.execute(
            f"WITH ordered AS MATERIALIZED "
            f"(SELECT {RECORDS_ALIAS}.id AS id, {alias}.{quote_identifier(order.column)} AS v {joined}), "
            "target AS (SELECT id, v FROM ordered WHERE id = ?) "
            "SELECT "
            f"(SELECT o.id FROM ordered o, target t WHERE {before} "
            f"ORDER BY o.v {backwards} NULLS FIRST, o.id DESC LIMIT 1), "
            f"(SELECT o.id FROM ordered o, target t WHERE NOT {before} AND o.id <> t.id "
            f"ORDER BY o.v {order.direction} NULLS LAST, o.id ASC LIMIT 1), "
            f"(SELECT COUNT(*) FROM ordered o, target t WHERE {before}) + 1, "
            "(SELECT COUNT(*) FROM ordered) "
            "FROM target",
            [record_id],
        ).fetchone()
        if located is not None:
            return {"prev": located[0], "next": located[1], "position": int(located[2]), "total": int(located[3])}
        total_row = connection.execute(f"SELECT COUNT(*) {joined}").fetchone()
    return {"prev": None, "next": None, "position": None, "total": int(total_row[0]) if total_row else 0}


def matching_record_ids(dataset: Dataset, where: str | None, computed_filter: ComputedFilter | None) -> list[str]:
    """The records matching both conditions, in no particular order.

    Raises:
        InvalidRecordFilter: LanceDB refused `where`.
    """
    record_rows, computed_rows = _rows(dataset, where, computed_filter, BY_ID)
    with duckdb.connect() as connection:
        joined = _joined(connection, record_rows, computed_rows, computed_filter)
        return [row[0] for row in connection.execute(f"SELECT {RECORDS_ALIAS}.id {joined}").fetchall()]


def matching_records(
    dataset: Dataset,
    cross_filter: CrossFilter,
    record_columns: Sequence[str] = (),
    computed_columns: Sequence[str] = (),
    apart: Collection[str] = (),
) -> pa.Table:
    """The records a request keeps, with some of their own columns and computed ones; the filters of the
    columns `apart` told rather than applied.

    For each column apart the request filters, a column named `KEPT_BY_PREFIX` and its name says
    whether its filters keep the record — not where its value is none, as a filter keeps no such
    record. The request keeps the records for which each of them is true; the overview counts a card
    over those every other column's filters keep (§22.7).

    Args:
        dataset: The dataset.
        cross_filter: The request, its filters per column.
        record_columns: The records' columns to read, beside their `id`.
        computed_columns: The computed columns to read, each named `COMPUTED_COLUMN_PREFIX` and its name;
            none where a record has no value, or no table holds the column.
        apart: The columns, as the explorer names them, whose filters are told rather than applied.

    Returns:
        A row per record the filters of the other columns keep, in no particular order.

    Raises:
        InvalidRecordFilter: LanceDB refused the request's condition on the records.
    """
    told = {column: sql for column, sql in cross_filter.on_records.items() if column in apart}
    applied = [sql for column, sql in cross_filter.on_records.items() if column not in apart]
    where = _all_of([condition for condition in (cross_filter.where, *applied) if condition is not None])
    columns = list(dict.fromkeys(["id", *record_columns]))
    projection: list[str] | dict[str, str] = columns
    if told:
        # A column's filters are a condition of the read, as they would be of its `where`: they say
        # alike whatever the column holds. A record's columns go through by name.
        projection = {
            **{column: _lance_identifier(column) for column in columns},
            **{KEPT_BY_PREFIX + column: f"coalesce(({sql}), false)" for column, sql in told.items()},
        }
    record_rows = _record_rows(dataset, projection, where)
    told_computed = {column: filter_ for column, filter_ in cross_filter.on_computed.items() if column in apart}
    computed_filter = _all_computed_of(
        [filter_ for column, filter_ in cross_filter.on_computed.items() if column not in apart]
    )
    read = [
        *(computed_filter.columns if computed_filter is not None else ()),
        *(column for filter_ in told_computed.values() for column in filter_.columns),
        *computed_columns,
    ]
    computed_rows = _computed(dataset, list(dict.fromkeys(read)))
    selected = [
        f"{RECORDS_ALIAS}.*",
        *(
            f"{computed_sql_column(column)} AS {quote_identifier(COMPUTED_COLUMN_PREFIX + column)}"
            for column in computed_columns
        ),
        *(
            f"coalesce(({filter_.sql}), false) AS {quote_identifier(KEPT_BY_PREFIX + column)}"
            for column, filter_ in told_computed.items()
        ),
    ]
    with duckdb.connect() as connection:
        joined = _joined(connection, record_rows, computed_rows, computed_filter)
        return connection.execute(f"SELECT {', '.join(selected)} {joined}").to_arrow_table()


def _all_of(conditions: Sequence[str]) -> str | None:
    """The conditions joined, each kept whole; None for none."""
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else " AND ".join(f"({condition})" for condition in conditions)


def _all_computed_of(filters: Sequence[ComputedFilter]) -> ComputedFilter | None:
    """Conditions on computed columns joined into one, which reads the columns of each; None for none."""
    sql = _all_of([filter_.sql for filter_ in filters])
    if sql is None:
        return None
    return ComputedFilter(sql=sql, columns=tuple(dict.fromkeys(column for one in filters for column in one.columns)))


def _lance_identifier(name: str) -> str:
    """A column's name as LanceDB's SQL reads it whatever it is, a keyword included: between backticks."""
    return "`" + name.replace("`", "``") + "`"


def computed_values(dataset: Dataset, record_ids: Sequence[str], columns: Sequence[str]) -> dict[str, dict[str, Any]]:
    """The values of some computed columns for some records.

    A computed table that cannot be read is logged and answers none, as before any computation: a
    page of records shows no value of its columns rather than failing.

    Args:
        dataset: The dataset.
        record_ids: The records.
        columns: The computed columns.

    Returns:
        For each record that has a value computed, the value of each column it holds.
    """
    if not record_ids or not columns:
        return {}
    values: dict[str, dict[str, Any]] = {}
    for start in range(0, len(record_ids), IDS_PER_QUERY):
        batch = list(record_ids[start : start + IDS_PER_QUERY])
        rows = _read_statistics(dataset, list(columns), f"record_id IN {to_sql_list(batch)}")
        if rows is None:
            return {}
        for row in rows.to_pylist():
            values[row.pop("record_id")] = row
    return values


def _rows(
    dataset: Dataset, where: str | None, computed_filter: ComputedFilter | None, order: RecordOrder
) -> tuple[pa.Table, pa.Table]:
    """The records' identifiers matching `where`, with the record column sorted on, and the
    computed columns the filter or the order reads.
    """
    record_columns = ["id"]
    if not order.on_computed and order.column != "id":
        record_columns.append(order.column)
    record_rows = _record_rows(dataset, record_columns, where)
    computed_columns = list(computed_filter.columns) if computed_filter is not None else []
    if order.on_computed and order.column not in computed_columns:
        computed_columns.append(order.column)
    return record_rows, _computed(dataset, computed_columns)


def _record_rows(dataset: Dataset, columns: list[str] | dict[str, str], where: str | None) -> pa.Table:
    """These columns of the records matching `where`, all of them.

    Raises:
        InvalidRecordFilter: LanceDB refused `where`.
    """
    try:
        return _read(dataset.open_table(_RECORDS_TABLE), columns, where)
    except RuntimeError as error:
        # The compiled conditions are allowlisted and cannot be malformed: only a raw clause is.
        raise InvalidRecordFilter(str(error)) from error


def _joined(
    connection: duckdb.DuckDBPyConnection,
    record_rows: pa.Table,
    computed_rows: pa.Table,
    computed_filter: ComputedFilter | None,
) -> str:
    """The records joined with the columns computed from them, as the FROM clause of a query, the
    filter applied.

    A record has one row of computed columns: should two be stored — two merges on S3, where no lock
    holds them apart — one of them is kept, so that no record shows twice.
    """
    connection.register("record_rows", record_rows)
    connection.register("computed_rows", computed_rows)
    joined = (
        f"FROM record_rows {RECORDS_ALIAS} LEFT JOIN "
        f"(SELECT * FROM computed_rows QUALIFY ROW_NUMBER() OVER (PARTITION BY record_id) = 1) "
        f"{COMPUTED_ALIAS} ON {RECORDS_ALIAS}.id = {COMPUTED_ALIAS}.record_id"
    )
    if computed_filter is not None:
        joined += f" WHERE {computed_filter.sql}"
    return joined


def _order_by(order: RecordOrder) -> str:
    """The order of the join: the column asked, those without a value last, then the identifiers."""
    alias = COMPUTED_ALIAS if order.on_computed else RECORDS_ALIAS
    return f"{alias}.{quote_identifier(order.column)} {order.direction} NULLS LAST, {RECORDS_ALIAS}.id ASC"


def _read(table: Any, columns: list[str] | dict[str, str], where: str | None) -> pa.Table:
    """The columns of the rows of a LanceDB table that match a condition, all of them: named, or each
    computed by an expression of its own (a projection).
    """
    # LanceDB applies its default limit of ten rows unless told otherwise; a limit of zero is refused.
    query = table.search(None).select(columns).limit(max(table.count_rows(), 1))
    if where is not None:
        query = query.where(where)
    return query.to_arrow()


def _read_statistics(dataset: Dataset, columns: list[str], where: str | None) -> pa.Table | None:
    """These columns of the statistics table, those it holds, with each row's record; None before
    any computation, or when the table cannot be read.
    """
    if RECORD_STATISTICS_TABLE not in dataset.info.tables:
        return None
    return read_latest(dataset, RECORD_STATISTICS_TABLE, ["record_id", *columns], where, required=["record_id"])


def read_latest(
    dataset: Dataset, table_name: str, columns: list[str], where: str | None, required: list[str]
) -> pa.Table | None:
    """These columns of a computed table, those it holds, at its latest version; None when the
    table cannot be read, or lacks a column it must hold — logged.

    A job compacting the table during the read can take the files of the version read away: the read
    is tried again once, on the version the compaction made. A table lacking a column it must hold is
    not read again: it would lack it still.

    Args:
        dataset: The dataset.
        table_name: The computed table.
        columns: The columns to read; those the table does not hold are left out.
        where: The condition the rows read meet, as LanceDB reads it; None for every row.
        required: The columns the table must hold to be read at all.

    Returns:
        The rows read, or None.
    """
    failure: Exception | None = None
    for _attempt in range(_READ_ATTEMPTS):
        try:
            table = dataset.open_latest_table(table_name)
            held = table.schema.names
        except Exception as error:  # noqa: BLE001 - a broken table shows no value, it fails no page
            failure = error
            continue
        missing = [column for column in required if column not in held]
        if missing:
            # Not read again: it would lack them still.
            failure = ValueError(f"it holds no column {', '.join(missing)}")
            break
        present = [column for column in columns if column in held]
        try:
            return _read(table, present, where)
        except Exception as error:  # noqa: BLE001 - a broken table shows no value, it fails no page
            failure = error
    logger.warning(
        "Dataset %s: its table %s cannot be read, none of it shown: %s", dataset.info.id, table_name, failure
    )
    return None


def _computed(dataset: Dataset, columns: list[str]) -> pa.Table:
    """The records' computed columns: their record and these columns, none where no table holds
    them — before any computation, or when one cannot be read.
    """
    rows = _read_statistics(dataset, columns, None)
    if rows is None:
        rows = pa.table({"record_id": pa.array([], pa.string())})
    for column in columns:
        if column not in rows.schema.names:
            rows = rows.append_column(column, pa.nulls(rows.num_rows, pa.float64()))
    return rows
