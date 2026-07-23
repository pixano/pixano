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

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pixano.datasets.dataset_schema import serialize_all_fields
from pixano.schemas.records import Record
from pixano.utils.python import quote_sql_string


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
            )
        )

    descriptors.sort(key=lambda d: (d.source != "base", d.name))
    return descriptors


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


def _coerce_scalar(value: str, col_type: str, column: str) -> str:
    """Coerce a raw string value to a SQL literal for a scalar column."""
    if len(value) > MAX_VALUE_LENGTH:
        raise FilterCompileError(f"Value for '{column}' exceeds {MAX_VALUE_LENGTH} characters.")
    if col_type == "str":
        return quote_sql_string(value)
    if col_type == "int":
        try:
            return str(int(value))
        except ValueError:
            raise FilterCompileError(f"'{value}' is not a valid integer for column '{column}'.") from None
    if col_type == "float":
        try:
            return repr(float(value))
        except ValueError:
            raise FilterCompileError(f"'{value}' is not a valid number for column '{column}'.") from None
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
    return quote_sql_string(dt.isoformat(sep=" "))


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
    column, col_type = descriptor.name, descriptor.type

    if col_type == "datetime":
        return _compile_datetime_clause(column, op, raw)

    if op in {"in", "nin"}:
        values = [v for v in _unescape_list(raw) if v != ""]
        if not values:
            raise FilterCompileError(f"'{op}' on '{column}' needs at least one value.")
        literals = ", ".join(_coerce_scalar(v, col_type, column) for v in values)
        keyword = "IN" if op == "in" else "NOT IN"
        return f"{column} {keyword} ({literals})"

    if op == "contains":
        if col_type != "str":
            raise FilterCompileError(f"'contains' is only valid on string columns (got '{column}').")
        if len(raw) > MAX_VALUE_LENGTH:
            raise FilterCompileError(f"Value for '{column}' exceeds {MAX_VALUE_LENGTH} characters.")
        pattern = quote_sql_string(f"%{_escape_like(raw)}%")
        return f"{column} LIKE {pattern} ESCAPE '\\'"

    literal = _coerce_scalar(raw, col_type, column)
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
