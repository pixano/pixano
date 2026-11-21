# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Explorer filter/sort compiler.

Pure module (no FastAPI) that turns the explorer's declarative query — repeated
``filter=col:op:value`` params plus a free-text ``q`` — into a safe LanceDB SQL
``where`` clause, and validates the requested sort. Every column, operator and
value is checked against a per-dataset catalogue built from the record schema, so
a malformed query is a caught `FilterCompileError` (mapped to HTTP 400) rather
than raw SQL reaching the engine.

The catalogue is also serialized to the frontend via ``GET /datasets/{id}/filters``
so the UI offers exactly the columns, operators and enumerable values the backend
will accept — no more reverse-engineering columns from page rows.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pixano.datasets.dataset_schema import serialize_all_fields
from pixano.datasets.queries.computed_columns import (
    RECORD_STATISTICS_TABLE,
    ComputedFilter,
    CrossFilter,
    RecordOrder,
    computed_sql_column,
)
from pixano.schemas import SchemaGroup
from pixano.schemas.records import Record
from pixano.statistics.definitions import StatisticLevel
from pixano.utils.python import quote_sql_string


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from pixano.datasets import Dataset


# --- Limits (defensive caps; each violation is a distinct 400) ---------------

MAX_FILTERS = 8
MAX_VALUE_LENGTH = 512
MAX_Q_LENGTH = 256

# --- Operators allowed per column type ---------------------------------------
# `contains` (str), `ne`/`nin` (all) are NOT served correctly by a scalar index
# (they match the complement / a substring), so a filter using them forces the
# safe full-scan path — see `NON_SERVABLE_OPERATORS` and TableQueryBuilder.
FILTER_OPERATORS: dict[str, tuple[str, ...]] = {
    "str": ("eq", "ne", "in", "nin", "contains"),
    "int": ("eq", "ne", "lt", "lte", "gt", "gte", "in", "nin"),
    "float": ("eq", "ne", "lt", "lte", "gt", "gte"),
    "bool": ("eq", "ne"),
    "datetime": ("eq", "lt", "lte", "gt", "gte", "between"),
}

# Operators a scalar index cannot serve as a bounded head-of-table scan.
NON_SERVABLE_OPERATORS = frozenset({"ne", "nin", "contains"})

# Base record columns that expose a small, enumerable value set worth listing.
_ENUMERABLE_COLUMNS = frozenset({"split", "status"})
# Hard cap on distinct values returned for an enumerable column.
_MAX_ENUMERABLE_VALUES = 100

_BASE_RECORD_FIELDS = frozenset(Record.model_fields.keys())

_SCALAR_TYPES = frozenset(FILTER_OPERATORS.keys())

#: What names a statistic among the records' columns: its table, then its column. The table keeps a
#: statistic apart from a record's own column of the same name (backend-processing §22).
STATISTICS_COLUMN_PREFIX = f"{RECORD_STATISTICS_TABLE}."
_STATISTICS_SOURCE = "statistics"

# The integers a column holds, 64-bit: a literal beyond them fails the query rather than compare.
_MIN_INT64 = -(2**63)
_MAX_INT64 = 2**63 - 1


class FilterCompileError(ValueError):
    """A filter/sort could not be compiled from the request (→ HTTP 400)."""


@dataclass(frozen=True)
class ColumnDescriptor:
    """One filterable/sortable column, as published to the frontend.

    Attributes:
        name: Column name.
        type: Scalar type name (``str``/``int``/``float``/``bool``/``datetime``)
            or the raw schema type for non-scalar columns.
        collection: Whether the column is a ``list[...]`` (not filterable in 0.8).
        source: ``"base"`` for a `Record` field, ``"custom"`` for a spec attr.
        filterable: Whether the column can appear in a ``filter=`` clause.
        sortable: Whether the column can be sorted on.
        searchable: Whether the column participates in the free-text ``q`` sweep.
        indexed: Whether the column carries a scalar index.
        operators: Operators allowed for this column (empty if not filterable).
        values: Enumerable values (split/status), else ``None``.
        values_complete: Whether ``values`` is exhaustive (not truncated).
        table: The table the column is read from: the records', or their statistics'.
        label: What a person reads in place of the name, for a statistic.
        unit: The unit of a statistic's values, if they have one.
    """

    name: str
    type: str
    collection: bool
    source: str
    filterable: bool
    sortable: bool
    searchable: bool
    indexed: bool
    operators: tuple[str, ...]
    values: tuple[str, ...] | None
    values_complete: bool
    table: str = SchemaGroup.RECORD.value
    label: str | None = None
    unit: str | None = None


# Per-(dataset, table, version) cache of enumerable column values.
_enum_cache: dict[tuple[str, str, int], dict[str, tuple[tuple[str, ...], bool]]] = {}


def _indexed_columns(table) -> set[str]:  # noqa: ANN001 - lancedb table
    indexed: set[str] = set()
    try:
        for index in table.list_indices():
            indexed.update(getattr(index, "columns", None) or [])
    except Exception:  # pragma: no cover - lancedb introspection failure
        pass
    return indexed


def _enumerable_values(dataset: "Dataset", table_name: str, column: str) -> tuple[tuple[str, ...], bool]:
    """Return ``(values, complete)`` for a low-cardinality column, cached on version."""
    from pixano.datasets.queries import TableQueryBuilder

    table = dataset.open_table(table_name)
    cache_key = (dataset.info.id, table_name, int(table.version))
    cached = _enum_cache.get(cache_key)
    if cached is not None and column in cached:
        return cached[column]

    rows = (
        TableQueryBuilder(table, dataset._db_connection)  # noqa: SLF001
        .select([column])
        .limit(table.count_rows())
        .to_list()
    )
    seen: list[str] = []
    seen_set: set[str] = set()
    complete = True
    for row in rows:
        value = row.get(column)
        if value is None:
            continue
        value = str(value)
        if value in seen_set:
            continue
        if len(seen) >= _MAX_ENUMERABLE_VALUES:
            complete = False
            break
        seen_set.add(value)
        seen.append(value)
    result = (tuple(sorted(seen)), complete)
    _enum_cache.setdefault(cache_key, {})[column] = result
    return result


def build_column_catalogue(dataset: "Dataset", table_name: str = "records") -> list[ColumnDescriptor]:
    """Build the filterable/sortable column catalogue for a dataset table.

    Args:
        dataset: The dataset.
        table_name: Table to describe (defaults to the record table).

    Returns:
        One `ColumnDescriptor` per column present in both the schema manifest and
        the physical table, ordered with base columns first.
    """
    schema = dataset.info.tables[table_name]
    fields = serialize_all_fields(schema)
    table = dataset.open_table(table_name)
    physical = set(table.schema.names)
    indexed = _indexed_columns(table)

    descriptors: list[ColumnDescriptor] = []
    for name, descriptor in fields.items():
        if name not in physical:
            continue
        col_type = descriptor["type"]
        collection = bool(descriptor.get("collection"))
        source = "base" if name in _BASE_RECORD_FIELDS else "custom"
        scalar = col_type in _SCALAR_TYPES and not collection
        filterable = scalar
        sortable = scalar
        searchable = col_type == "str" and not collection and (name == "comment" or source == "custom")
        operators = FILTER_OPERATORS.get(col_type, ()) if filterable else ()

        values: tuple[str, ...] | None = None
        values_complete = True
        if name in _ENUMERABLE_COLUMNS and scalar:
            values, values_complete = _enumerable_values(dataset, table_name, name)

        descriptors.append(
            ColumnDescriptor(
                name=name,
                type=col_type,
                collection=collection,
                source=source,
                filterable=filterable,
                sortable=sortable,
                searchable=searchable,
                indexed=name in indexed,
                operators=operators,
                values=values,
                values_complete=values_complete,
                table=table_name,
            )
        )

    descriptors.sort(key=lambda d: (d.source != "base", d.name))
    if table_name == SchemaGroup.RECORD.value:
        descriptors += _statistic_descriptors(dataset)
    return descriptors


def _statistic_descriptors(dataset: "Dataset") -> list[ColumnDescriptor]:
    """The statistics the dataset computed per record whose column is there, as columns of the records.

    A statistics table that cannot be opened is logged and offers none: the explorer of the dataset
    keeps working on the records' own columns.
    """
    recorded = [computed for computed in dataset.info.statistics if computed.definition.level is StatisticLevel.RECORD]
    if not recorded or RECORD_STATISTICS_TABLE not in dataset.info.tables:
        return []
    try:
        physical = set(dataset.open_latest_table(RECORD_STATISTICS_TABLE).schema.names)
    except Exception as error:  # noqa: BLE001 - a broken table offers no statistic, it fails no page
        logger.warning("Dataset %s: its statistics cannot be read, none offered: %s", dataset.info.id, error)
        return []
    columns = []
    for computed in recorded:
        definition = computed.definition
        if definition.name not in physical:
            continue
        columns.append(
            ColumnDescriptor(
                name=f"{STATISTICS_COLUMN_PREFIX}{definition.name}",
                type=definition.value_type,
                collection=False,
                source=_STATISTICS_SOURCE,
                filterable=True,
                sortable=True,
                searchable=False,
                indexed=False,
                operators=FILTER_OPERATORS[definition.value_type],
                values=None,
                values_complete=True,
                table=RECORD_STATISTICS_TABLE,
                label=definition.label,
                unit=definition.unit or None,
            )
        )
    return sorted(columns, key=lambda column: (column.label or column.name, column.name))


def computed_columns_by_name(catalogue: list[ColumnDescriptor]) -> dict[str, str]:
    """The computed columns the catalogue offers, for the values a page shows: their column in the
    join, by the name the catalogue gives them.
    """
    return {
        descriptor.name: _computed_column(descriptor)
        for descriptor in catalogue
        if descriptor.table == RECORD_STATISTICS_TABLE
    }


def _computed_column(descriptor: ColumnDescriptor) -> str:
    """The column of the join a computed column's descriptor names: a statistic's column of its table."""
    return descriptor.name.removeprefix(STATISTICS_COLUMN_PREFIX)


def _is_computed(descriptor: ColumnDescriptor) -> bool:
    """Whether a column was computed from the records, in a table of its own: a statistic's."""
    return descriptor.table == RECORD_STATISTICS_TABLE


def _sql_column(descriptor: ColumnDescriptor) -> str:
    """How a condition names the column: a record's as is, a computed one as the join reads it."""
    if _is_computed(descriptor):
        return computed_sql_column(_computed_column(descriptor))
    return descriptor.name


# --- Value parsing / SQL rendering -------------------------------------------


def _unescape_list(raw: str) -> list[str]:
    r"""Split a list value on unescaped commas, unescaping ``\,`` and ``\\``."""
    items: list[str] = []
    current: list[str] = []
    escaped = False
    for char in raw:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    if escaped:  # trailing backslash → literal backslash
        current.append("\\")
    items.append("".join(current))
    return items


def _coerce_scalar(value: str, col_type: str, column: str, through_duckdb: bool = False) -> str:
    """Coerce a raw string value to a SQL literal for a scalar column.

    A condition on a computed column is read by DuckDB (`through_duckdb`), which reads a number
    written with a decimal point as a DECIMAL: turned into a double, one of seventeen digits can miss
    the double it was written from by its last bit — a filter on a bar's start would then leave out
    the very value the bar starts at. Written as text, the number is read back exactly.
    """
    if len(value) > MAX_VALUE_LENGTH:
        raise FilterCompileError(f"Value for '{column}' exceeds {MAX_VALUE_LENGTH} characters.")
    if col_type == "str":
        return quote_sql_string(value)
    if col_type == "int":
        try:
            number = int(value)
        except ValueError:
            raise FilterCompileError(f"'{value}' is not a valid integer for column '{column}'.") from None
        if not _MIN_INT64 <= number <= _MAX_INT64:
            raise FilterCompileError(f"'{value}' is beyond the integers column '{column}' holds.")
        return str(number)
    if col_type == "float":
        try:
            decimal = float(value)
        except ValueError:
            raise FilterCompileError(f"'{value}' is not a valid number for column '{column}'.") from None
        # SQL has no literal for these: `nan` would be read as the name of a column.
        if not math.isfinite(decimal):
            raise FilterCompileError(f"'{value}' is not a finite number for column '{column}'.")
        return f"CAST({quote_sql_string(repr(decimal))} AS DOUBLE)" if through_duckdb else repr(decimal)
    if col_type == "bool":
        lowered = value.strip().lower()
        if lowered in {"true", "1"}:
            return "true"
        if lowered in {"false", "0"}:
            return "false"
        raise FilterCompileError(f"'{value}' is not a valid boolean for column '{column}'.")
    raise FilterCompileError(f"Column '{column}' of type '{col_type}' is not filterable.")


def _parse_datetime(value: str, column: str) -> tuple[datetime, bool]:
    """Parse an ISO date or datetime; return ``(dt, date_only)``. Naive-local."""
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise FilterCompileError(f"'{value}' is not a valid ISO date/datetime for column '{column}'.") from None
    date_only = len(text) == 10  # "YYYY-MM-DD"
    return parsed, date_only


def _dt_literal(dt: datetime) -> str:
    # DataFusion (LanceDB's filter engine) does not implicitly cast a string to
    # a timestamp column, so a bare quoted string fails; emit a typed timestamp
    # literal instead. Microsecond precision round-trips.
    return f"timestamp {quote_sql_string(dt.isoformat(sep=' '))}"


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so a substring search matches literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _compile_datetime_clause(column: str, op: str, raw: str) -> str:
    if op == "between":
        parts = _unescape_list(raw)
        if len(parts) != 2:
            raise FilterCompileError(f"'between' on '{column}' needs exactly two values.")
        lo, _ = _parse_datetime(parts[0], column)
        hi, hi_date_only = _parse_datetime(parts[1], column)
        if hi_date_only:
            hi = hi + timedelta(days=1)
            return f"({column} >= {_dt_literal(lo)} AND {column} < {_dt_literal(hi)})"
        return f"({column} >= {_dt_literal(lo)} AND {column} <= {_dt_literal(hi)})"

    dt, date_only = _parse_datetime(raw, column)
    if op == "eq":
        # A date-only equality means "anytime that day": [day, day+1).
        if date_only:
            return f"({column} >= {_dt_literal(dt)} AND {column} < {_dt_literal(dt + timedelta(days=1))})"
        return f"{column} = {_dt_literal(dt)}"
    sql_op = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}[op]
    return f"{column} {sql_op} {_dt_literal(dt)}"


def _compile_clause(descriptor: ColumnDescriptor, op: str, raw: str) -> str:
    # The SQL names the column as the query reading it does; a message names it as the catalogue does.
    column, name, col_type = _sql_column(descriptor), descriptor.name, descriptor.type
    through_duckdb = _is_computed(descriptor)

    if col_type == "datetime":
        return _compile_datetime_clause(column, op, raw)

    if op in {"in", "nin"}:
        values = [v for v in _unescape_list(raw) if v != ""]
        if not values:
            raise FilterCompileError(f"'{op}' on '{name}' needs at least one value.")
        literals = ", ".join(_coerce_scalar(v, col_type, name, through_duckdb) for v in values)
        keyword = "IN" if op == "in" else "NOT IN"
        return f"{column} {keyword} ({literals})"

    if op == "contains":
        if col_type != "str":
            raise FilterCompileError(f"'contains' is only valid on string columns (got '{name}').")
        if len(raw) > MAX_VALUE_LENGTH:
            raise FilterCompileError(f"Value for '{name}' exceeds {MAX_VALUE_LENGTH} characters.")
        pattern = quote_sql_string(f"%{_escape_like(raw)}%")
        return f"{column} LIKE {pattern} ESCAPE '\\'"

    literal = _coerce_scalar(raw, col_type, name, through_duckdb)
    sql_op = {"eq": "=", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}[op]
    return f"{column} {sql_op} {literal}"


def _split_filter(token: str) -> tuple[str, str, str]:
    """Split ``col:op:value`` into three parts (value may contain further ``:``)."""
    first = token.find(":")
    second = token.find(":", first + 1)
    if first == -1 or second == -1:
        raise FilterCompileError(f"Filter '{token}' must be of the form 'column:operator:value'.")
    return token[:first], token[first + 1 : second], token[second + 1 :]


def _compile_q(catalogue: dict[str, ColumnDescriptor], q: str) -> str:
    """Compile the free-text sweep over searchable string columns."""
    if len(q) > MAX_Q_LENGTH:
        raise FilterCompileError(f"Search text exceeds {MAX_Q_LENGTH} characters.")
    columns = [d.name for d in catalogue.values() if d.searchable]
    if not columns:
        # No searchable column → a query that matches nothing rather than
        # silently ignoring the user's text.
        return "false"
    pattern = quote_sql_string(f"%{_escape_like(q.lower())}%")
    clauses = [f"lower({column}) LIKE {pattern} ESCAPE '\\'" for column in columns]
    return "(" + " OR ".join(clauses) + ")"


def compile_filters(
    catalogue: list[ColumnDescriptor],
    filters: list[str] | None,
    q: str | None = None,
) -> tuple[str | None, set[str], bool]:
    """Compile filter tokens + free text into a safe SQL where clause.

    Args:
        catalogue: The column catalogue for the table.
        filters: ``col:op:value`` tokens, AND-composed.
        q: Free-text search over searchable string columns.

    Returns:
        ``(where, referenced_columns, index_servable)`` — ``where`` is ``None``
        when there is nothing to filter; ``index_servable`` is ``False`` when any
        clause uses an operator a scalar index can't serve (so the caller must
        force a full scan).

    Raises:
        FilterCompileError: On any unknown column, bad operator, unparseable
            value, or a reserved/over-limit request.
    """
    by_name = {d.name: d for d in catalogue}
    filters = filters or []
    if len(filters) > MAX_FILTERS:
        raise FilterCompileError(f"At most {MAX_FILTERS} filters are allowed (got {len(filters)}).")

    clauses: list[str] = []
    referenced: set[str] = set()
    index_servable = True

    for token in filters:
        column, op, raw = _split_filter(token)
        if "." in column:
            raise FilterCompileError(f"Cross-table filters ('{column}') are planned for a future release.")
        descriptor = by_name.get(column)
        if descriptor is None:
            raise FilterCompileError(f"Unknown column '{column}'. Call GET /datasets/{{id}}/filters for the list.")
        if not descriptor.filterable:
            raise FilterCompileError(f"Column '{column}' is not filterable.")
        if op not in descriptor.operators:
            allowed = ", ".join(descriptor.operators)
            raise FilterCompileError(f"Operator '{op}' is not valid for '{column}' (allowed: {allowed}).")
        clauses.append(_compile_clause(descriptor, op, raw))
        referenced.add(column)
        if op in NON_SERVABLE_OPERATORS:
            index_servable = False

    if q is not None and q != "":
        clauses.append(_compile_q(by_name, q))
        index_servable = False  # LIKE sweep is never index-served
        referenced.update(d.name for d in catalogue if d.searchable)

    if not clauses:
        return None, referenced, True
    return " AND ".join(clauses), referenced, index_servable


def split_filters(filters: list[str] | None) -> tuple[list[str], list[str]]:
    """Tell the filters on the records' own columns from those on the columns computed from them.

    A computed column is named after its table (`STATISTICS_COLUMN_PREFIX`), so that one the dataset
    did not compute is told apart too, and refused as such.

    Args:
        filters: ``col:op:value`` tokens.

    Returns:
        The tokens on the records' columns, for `compile_filters`, and those on their computed
        columns, for `compile_computed_filters`.

    Raises:
        FilterCompileError: On more filters than allowed, or a token not of the form
            ``column:operator:value``.
    """
    filters = filters or []
    if len(filters) > MAX_FILTERS:
        raise FilterCompileError(f"At most {MAX_FILTERS} filters are allowed (got {len(filters)}).")
    own: list[str] = []
    on_computed: list[str] = []
    for token in filters:
        column, _op, _raw = _split_filter(token)
        (on_computed if column.startswith(STATISTICS_COLUMN_PREFIX) else own).append(token)
    return own, on_computed


def compile_computed_filters(catalogue: list[ColumnDescriptor], filters: list[str]) -> ComputedFilter | None:
    """Compile filters on the columns computed from the records into a condition the join reads.

    Args:
        catalogue: The column catalogue for the records.
        filters: ``col:op:value`` tokens on computed columns (`split_filters`), AND-composed.

    Returns:
        The condition and the computed columns it reads; None when there is nothing to filter.

    Raises:
        FilterCompileError: On a column the dataset did not compute, an operator its type does not
            take, or a value it cannot hold.
    """
    by_name = {descriptor.name: descriptor for descriptor in catalogue if descriptor.table == RECORD_STATISTICS_TABLE}
    clauses: list[str] = []
    columns: list[str] = []
    for token in filters:
        column, op, raw = _split_filter(token)
        descriptor = by_name.get(column)
        if descriptor is None:
            raise FilterCompileError(f"Unknown statistic '{column}'. Call GET /datasets/{{id}}/filters for the list.")
        if op not in descriptor.operators:
            allowed = ", ".join(descriptor.operators)
            raise FilterCompileError(f"Operator '{op}' is not valid for '{column}' (allowed: {allowed}).")
        clauses.append(_compile_clause(descriptor, op, raw))
        columns.append(_computed_column(descriptor))
    if not clauses:
        return None
    return ComputedFilter(sql=" AND ".join(clauses), columns=tuple(dict.fromkeys(columns)))


@dataclass(frozen=True)
class RecordQuery:
    """A request on the records, compiled: what LanceDB filters, and what the join with the columns
    computed from them does.

    Attributes:
        where: The condition on the records' own columns, a deprecated raw clause included; None
            for every record.
        index_servable: Whether a scalar index can serve `where`.
        computed_filter: The condition on their computed columns; None for none.
        order: How they are ordered.
    """

    where: str | None
    index_servable: bool
    computed_filter: ComputedFilter | None
    order: RecordOrder

    @property
    def through_computed(self) -> bool:
        """Whether columns computed from the records take part, filtered or sorted on: the join decides."""
        return self.computed_filter is not None or self.order.on_computed


def compile_record_query(
    catalogue: list[ColumnDescriptor],
    filters: list[str] | None,
    q: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    raw_where: str | None = None,
) -> RecordQuery:
    """Compile a request on the records: its filters, its free text, its sort.

    Args:
        catalogue: The column catalogue for the records.
        filters: ``col:op:value`` tokens, on the records' columns or on columns computed from them.
        q: Free-text search over searchable string columns.
        sort: The column to sort on, a record's or a computed one; ``id`` by default.
        order: ``asc`` (by default) or ``desc``.
        raw_where: A deprecated raw where clause on the records, added as is.

    Returns:
        The compiled request.

    Raises:
        FilterCompileError: On any filter or sort the catalogue refuses.
    """
    own, on_computed = split_filters(filters)
    where, _referenced, index_servable = compile_filters(catalogue, own, q)
    sortcol, normalized_order = validate_sort(catalogue, sort, order)
    if raw_where:
        where = f"({raw_where})" if where is None else f"{where} AND ({raw_where})"
    return RecordQuery(
        where=where,
        index_servable=index_servable,
        computed_filter=compile_computed_filters(catalogue, on_computed),
        order=record_order(catalogue, sortcol, normalized_order),
    )


def compile_cross_filter(
    catalogue: list[ColumnDescriptor],
    filters: list[str] | None,
    q: str | None = None,
    raw_where: str | None = None,
) -> CrossFilter:
    """Compile a request on the records per column filtered, so that each column's filters can be left out
    in turn: the overview counts a card over what the other columns' filters keep (backend-processing §22.7).

    Checked as `compile_record_query` checks it. The free text and a raw clause name no column: they
    apply to every card.

    Args:
        catalogue: The column catalogue for the records.
        filters: ``col:op:value`` tokens, on the records' columns or on columns computed from them.
        q: Free-text search over searchable string columns.
        raw_where: A deprecated raw where clause on the records, added as is.

    Returns:
        The compiled request, its filters per column.

    Raises:
        FilterCompileError: On any filter the catalogue refuses.
    """
    own, on_computed = split_filters(filters)
    where, _referenced, _index_servable = compile_filters(catalogue, [], q)
    if raw_where:
        where = f"({raw_where})" if where is None else f"{where} AND ({raw_where})"
    on_records: dict[str, str] = {}
    for column, tokens in _by_column(own).items():
        condition, _referenced, _index_servable = compile_filters(catalogue, tokens)
        if condition is not None:
            on_records[column] = condition
    computed: dict[str, ComputedFilter] = {}
    for column, tokens in _by_column(on_computed).items():
        compiled = compile_computed_filters(catalogue, tokens)
        if compiled is not None:
            computed[column] = compiled
    return CrossFilter(where=where, on_records=on_records, on_computed=computed)


def _by_column(filters: list[str]) -> dict[str, list[str]]:
    """Filter tokens by the column they name, in the order the columns first come."""
    grouped: dict[str, list[str]] = {}
    for token in filters:
        column, _op, _raw = _split_filter(token)
        grouped.setdefault(column, []).append(token)
    return grouped


def record_order(catalogue: list[ColumnDescriptor], sortcol: str, order: str) -> RecordOrder:
    """How records are ordered for a sort validated by `validate_sort`.

    Args:
        catalogue: The column catalogue for the records.
        sortcol: The column sorted on, a record's or a computed one.
        order: ``asc`` or ``desc``.

    Returns:
        The order, on a record's column or on a computed one.
    """
    descriptor = next((d for d in catalogue if d.name == sortcol), None)
    if descriptor is not None and descriptor.table == RECORD_STATISTICS_TABLE:
        return RecordOrder(column=_computed_column(descriptor), descending=order == "desc", on_computed=True)
    return RecordOrder(column=sortcol, descending=order == "desc", on_computed=False)


def validate_sort(
    catalogue: list[ColumnDescriptor],
    sort: str | None,
    order: str | None,
) -> tuple[str, str]:
    """Validate a sort request against the catalogue.

    Defaults to ``id ASC``. `Dataset.get_data` appends an ``id`` tie-break so the
    order is stable across pages; this returns the single validated column+order.

    Args:
        catalogue: The column catalogue.
        sort: Requested sort column (defaults to ``id``).
        order: Requested order, ``asc`` or ``desc`` (defaults to ``asc``).

    Returns:
        ``(sortcol, order)`` — validated and normalized.

    Raises:
        FilterCompileError: On an unknown or non-sortable column, or a bad order.
    """
    sortcol = sort or "id"
    normalized_order = (order or "asc").lower()
    if normalized_order not in {"asc", "desc"}:
        raise FilterCompileError(f"Sort order must be 'asc' or 'desc' (got '{order}').")
    descriptor = next((d for d in catalogue if d.name == sortcol), None)
    if descriptor is None:
        raise FilterCompileError(f"Unknown sort column '{sortcol}'.")
    if not descriptor.sortable:
        raise FilterCompileError(f"Column '{sortcol}' is not sortable.")
    return sortcol, normalized_order
