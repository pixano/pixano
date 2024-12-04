# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.utils.python import estimate_folder_size, get_super_type_from_dict, natural_key, unique_list


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
