# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.utils.python import get_super_type_from_dict, natural_key, quote_sql_string, to_sql_list, unique_list


class TestToSqlList:
    def test_single_string(self):
        assert to_sql_list("abc") == "('abc')"

    def test_multiple(self):
        assert to_sql_list(["a", "b"]) == "('a', 'b')"

    def test_single_element_list_has_no_trailing_comma(self):
        assert to_sql_list(["a"]) == "('a')"

    def test_deduplicates_preserving_order(self):
        assert to_sql_list(["b", "a", "b"]) == "('b', 'a')"

    def test_empty_yields_null_list_not_error(self):
        assert to_sql_list([]) == "(NULL)"

    def test_single_quotes_are_escaped(self):
        assert to_sql_list("o'brien") == "('o''brien')"
        assert to_sql_list(["a'b", "c"]) == "('a''b', 'c')"

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="must be strings"):
            to_sql_list([1, 2])


def test_quote_sql_string():
    assert quote_sql_string("plain") == "'plain'"
    assert quote_sql_string("O'Brien") == "'O''Brien'"


def test_natural_key():
    output = natural_key("string")
    assert output == ["string"]

    output = natural_key("231yolo1")
    assert output == ["", 231, "yolo", 1, ""]


@pytest.mark.skip("Not implemented")
def test_estimate_folder_size():
    pass


def test_get_super_type_from_dict():
    class TypeA:
        pass

    class TypeB(TypeA):
        pass

    class TypeC(TypeB):
        pass

    class TypeD(TypeB):
        pass

    dict_types = {
        "TypeA": TypeA,
        "TypeB": TypeB,
        "TypeD": TypeD,
    }
    assert get_super_type_from_dict(TypeA, dict_types) == TypeA
    assert get_super_type_from_dict(TypeB, dict_types) == TypeB
    assert get_super_type_from_dict(TypeC, dict_types) == TypeB
    assert get_super_type_from_dict(TypeD, dict_types) == TypeD
    assert get_super_type_from_dict(int, dict_types) is None


def test_unique_list():
    # Assert elements are unique in output
    input = [1, 2, 3, 4, 4, 5, 6]
    assert unique_list(input) == [1, 2, 3, 4, 5, 6]

    # Assert elements are unique in output
    input = [6, 5, 4, 3, 2, 1, 1]
    assert unique_list(input) == [6, 5, 4, 3, 2, 1]

    # Assert that is works also on strings,
    # that elements are unique in output, and that they
    # keep their order
    input = ["def", "def", "abc"]
    assert unique_list(input) == ["def", "abc"]
