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
from collections.abc import Sequence
from dataclasses import dataclass
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
    try:
        record_rows = _read(dataset.open_table(_RECORDS_TABLE), record_columns, where)
    except RuntimeError as error:
        # The compiled conditions are allowlisted and cannot be malformed: only a raw clause is.
        raise InvalidRecordFilter(str(error)) from error
    computed_columns = list(computed_filter.columns) if computed_filter is not None else []
    if order.on_computed and order.column not in computed_columns:
        computed_columns.append(order.column)
    return record_rows, _computed(dataset, computed_columns)


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


def _read(table: Any, columns: list[str], where: str | None) -> pa.Table:
    """The columns of the rows of a LanceDB table that match a condition, all of them."""
    # LanceDB applies its default limit of ten rows unless told otherwise; a limit of zero is refused.
    query = table.search(None).select(columns).limit(max(table.count_rows(), 1))
    if where is not None:
        query = query.where(where)
    return query.to_arrow()


def _read_statistics(dataset: Dataset, columns: list[str], where: str | None) -> pa.Table | None:
    """These columns of the statistics table, those it holds, with each row's record, at its latest
    version; None before any computation, or when the table cannot be read — logged.

    A compaction of the table during the read can take the files of the version read away: the read
    is tried again once, on the version the compaction made.
    """
    if RECORD_STATISTICS_TABLE not in dataset.info.tables:
        return None
    failure: Exception | None = None
    for _attempt in range(_READ_ATTEMPTS):
        try:
            table = dataset.open_latest_table(RECORD_STATISTICS_TABLE)
            present = [column for column in columns if column in table.schema.names]
            return _read(table, ["record_id", *present], where)
        except Exception as error:  # noqa: BLE001 - a broken table shows no statistic, it fails no page
            failure = error
    logger.warning("Dataset %s: its statistics cannot be read, none shown: %s", dataset.info.id, failure)
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
