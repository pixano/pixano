# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.utils.python import get_super_type_from_dict, natural_key


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
