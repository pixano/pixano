# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.features.types.base_type import BaseType
from pixano.features.types.registry import _TYPES_REGISTRY, _register_type_internal


def test_register_type_internal():
    class TestType(BaseType):
        pass

    # Test 1: type is not registered
    assert TestType.__name__ not in _TYPES_REGISTRY

    _register_type_internal(TestType)

    # Test 2: type is registered
    assert TestType.__name__ in _TYPES_REGISTRY

    # Test 3: type cannot be registered twice
    with pytest.raises(
        ValueError,
        match=(
            "Type <class 'tests.features.types.test_registry.test_register_type_internal."
            "<locals>.TestType'> already registered"
        ),
    ):
        _register_type_internal(TestType)

    class NotBaseType:
        pass

    # Test 4: type must be a BaseModel
    with pytest.raises(
        ValueError, match=("Table type <class 'type'> must be a an atomic python type or derive from BaseType.")
    ):
        _register_type_internal(NotBaseType)
