# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest

from pixano.utils.python import (
    estimate_folder_size,
    fn_sort_dict,
    get_super_type_from_dict,
    natural_key,
    to_sql_list,
    unique_list,
)


def test_natural_key():
    output = natural_key("string")
    assert output == ["string"]

    output = natural_key("231yolo1")
    assert output == ["", 231, "yolo", 1, ""]


def test_estimate_folder_size(tmp_path: Path):
    for i in range(4):
        tmp_subfolder = tmp_path / f"folder_{i}"
        tmp_subfolder.mkdir()
        with open(tmp_subfolder / "file", "wb") as f:
            f.truncate(8192 * i)
    assert estimate_folder_size(tmp_path) == "48 KB"


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


def test_to_sql_list():
    assert to_sql_list("id1") == "('id1')"
    assert to_sql_list(["id1"]) == "('id1')"
    assert to_sql_list(["id1", "id2"]) == "('id1', 'id2')"

    with pytest.raises(ValueError, match="IDs must not be empty."):
        to_sql_list([])

    with pytest.raises(ValueError, match="IDs must be strings."):
        to_sql_list([0, 8])


def test_fn_sort_dict():
    dict_to_sort = {"a": 1, "b": "v", "c": False, "d": None, "e": 6}
    sorted_dict = fn_sort_dict(dict_to_sort, ["e", "d", "c", "b", "a"], [False, True, True, True, True])
    assert sorted_dict == (6, None, 0, "\x89", -1)

    with pytest.raises(
        ValueError,
        match="Cannot sort by <class 'list'> in descending order. "
        "Please use open an issue if you need this feature.",
    ):
        fn_sort_dict({"a": [0, 1]}, ["a"], [True])


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
