# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Unit tests for the pure explorer filter/sort compiler (`pixano.api.query`)."""

import pytest

from pixano.api.query import (
    FILTER_OPERATORS,
    ColumnDescriptor,
    FilterCompileError,
    compile_filters,
    validate_sort,
)


def _col(name: str, type_: str, *, source: str = "base", searchable: bool = False, indexed: bool = False):
    scalar = type_ in FILTER_OPERATORS
    return ColumnDescriptor(
        name=name,
        type=type_,
        collection=False,
        source=source,
        filterable=scalar,
        sortable=scalar,
        searchable=searchable,
        indexed=indexed,
        operators=FILTER_OPERATORS.get(type_, ()),
        values=None,
        values_complete=True,
    )


CATALOGUE = [
    _col("id", "str", indexed=True),
    _col("split", "str", indexed=True),
    _col("status", "str", indexed=True),
    _col("comment", "str", searchable=True),
    _col("caption", "str", source="custom", searchable=True),
    _col("score", "float"),
    _col("n", "int"),
    _col("ok", "bool"),
    _col("created_at", "datetime"),
    _col("vec", "NDArrayFloat"),  # non-scalar → not filterable/sortable
]


class TestGoldenSql:
    @pytest.mark.parametrize(
        "token,expected",
        [
            ("split:eq:train", "split = 'train'"),
            ("split:ne:train", "split != 'train'"),
            ("n:gte:5", "n >= 5"),
            ("n:lt:10", "n < 10"),
            ("score:gt:0.5", "score > 0.5"),
            ("ok:eq:true", "ok = true"),
            ("ok:eq:0", "ok = false"),
            ("split:in:train,val", "split IN ('train', 'val')"),
            ("n:nin:1,2", "n NOT IN (1, 2)"),
            ("caption:contains:a dog", "caption LIKE '%a dog%' ESCAPE '\\'"),
        ],
    )
    def test_operator_by_type(self, token: str, expected: str):
        where, _referenced, _servable = compile_filters(CATALOGUE, [token])
        assert where == expected

    def test_and_composition(self):
        where, referenced, _servable = compile_filters(CATALOGUE, ["split:eq:train", "n:gte:5"])
        assert where == "split = 'train' AND n >= 5"
        assert referenced == {"split", "n"}

    def test_quote_escaping(self):
        where, _r, _s = compile_filters(CATALOGUE, ["comment:eq:it's a % test"])
        assert where == "comment = 'it''s a % test'"

    def test_value_may_contain_colon(self):
        where, _r, _s = compile_filters(CATALOGUE, ["comment:eq:10:30:00"])
        assert where == "comment = '10:30:00'"

    def test_escaped_comma_in_list(self):
        where, _r, _s = compile_filters(CATALOGUE, ["split:in:a\\,b,c"])
        assert where == "split IN ('a,b', 'c')"

    def test_datetime_date_only_eq_is_a_day_range(self):
        where, _r, _s = compile_filters(CATALOGUE, ["created_at:eq:2026-07-20"])
        assert where == "(created_at >= '2026-07-20 00:00:00' AND created_at < '2026-07-21 00:00:00')"

    def test_datetime_between(self):
        where, _r, _s = compile_filters(CATALOGUE, ["created_at:between:2026-01-01,2026-07-20"])
        assert where == "(created_at >= '2026-01-01 00:00:00' AND created_at < '2026-07-21 00:00:00')"

    def test_free_text_sweeps_searchable_columns_lowercased(self):
        where, referenced, servable = compile_filters(CATALOGUE, [], q="Cat")
        assert where == "(lower(comment) LIKE '%cat%' ESCAPE '\\' OR lower(caption) LIKE '%cat%' ESCAPE '\\')"
        assert referenced == {"comment", "caption"}
        assert servable is False

    def test_free_text_escapes_wildcards(self):
        where, _r, _s = compile_filters(CATALOGUE, [], q="a_b%")
        assert "'%a\\_b\\%%' ESCAPE '\\'" in where


class TestServability:
    def test_servable_operators_keep_index_path(self):
        _w, _r, servable = compile_filters(CATALOGUE, ["split:eq:train", "n:gte:5"])
        assert servable is True

    @pytest.mark.parametrize("token", ["status:ne:new", "split:nin:train", "comment:contains:x"])
    def test_non_servable_operator_forces_full_scan(self, token: str):
        _w, _r, servable = compile_filters(CATALOGUE, [token])
        assert servable is False


class TestRejections:
    def test_unknown_column(self):
        with pytest.raises(FilterCompileError, match="Unknown column 'nope'"):
            compile_filters(CATALOGUE, ["nope:eq:x"])

    def test_bad_operator_for_type(self):
        with pytest.raises(FilterCompileError, match="Operator 'contains' is not valid for 'n'"):
            compile_filters(CATALOGUE, ["n:contains:5"])

    def test_non_integer_value(self):
        with pytest.raises(FilterCompileError, match="not a valid integer"):
            compile_filters(CATALOGUE, ["n:eq:abc"])

    def test_non_float_value(self):
        with pytest.raises(FilterCompileError, match="not a valid number"):
            compile_filters(CATALOGUE, ["score:eq:abc"])

    def test_non_filterable_type(self):
        with pytest.raises(FilterCompileError, match="not filterable"):
            compile_filters(CATALOGUE, ["vec:eq:1"])

    def test_cross_table_column_is_reserved(self):
        with pytest.raises(FilterCompileError, match="Cross-table filters"):
            compile_filters(CATALOGUE, ["entity.label:eq:person"])

    def test_too_many_filters(self):
        with pytest.raises(FilterCompileError, match="At most 8 filters"):
            compile_filters(CATALOGUE, ["split:eq:train"] * 9)

    def test_malformed_token(self):
        with pytest.raises(FilterCompileError, match="column:operator:value"):
            compile_filters(CATALOGUE, ["justacolumn"])

    def test_bad_datetime(self):
        with pytest.raises(FilterCompileError, match="not a valid ISO"):
            compile_filters(CATALOGUE, ["created_at:eq:not-a-date"])

    def test_between_needs_two_values(self):
        with pytest.raises(FilterCompileError, match="exactly two values"):
            compile_filters(CATALOGUE, ["created_at:between:2026-01-01"])


class TestSort:
    def test_default_sort_is_id_asc(self):
        assert validate_sort(CATALOGUE, None, None) == ("id", "asc")

    def test_valid_sort(self):
        assert validate_sort(CATALOGUE, "score", "desc") == ("score", "desc")

    def test_unknown_sort_column(self):
        with pytest.raises(FilterCompileError, match="Unknown sort column"):
            validate_sort(CATALOGUE, "nope", "asc")

    def test_non_sortable_column(self):
        with pytest.raises(FilterCompileError, match="not sortable"):
            validate_sort(CATALOGUE, "vec", "asc")

    def test_bad_order(self):
        with pytest.raises(FilterCompileError, match="must be 'asc' or 'desc'"):
            validate_sort(CATALOGUE, "id", "sideways")


class TestEmpty:
    def test_no_filters_no_query(self):
        assert compile_filters(CATALOGUE, []) == (None, set(), True)

    def test_empty_query_string_is_ignored(self):
        assert compile_filters(CATALOGUE, [], q="") == (None, set(), True)
