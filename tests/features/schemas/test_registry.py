# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.features import BaseSchema
from pixano.features.schemas.registry import (
    _PIXANO_SCHEMA_REGISTRY,
    _SCHEMA_REGISTRY,
    _register_schema_internal,
    register_schema,
)


def test_register_schema_internal():
    class TestSchema(BaseSchema):
        pass

    # Test 1: type is not registered
    assert TestSchema.__name__ not in _SCHEMA_REGISTRY
    assert TestSchema.__name__ not in _PIXANO_SCHEMA_REGISTRY

    _register_schema_internal(TestSchema)

    # Test 2: type is registered
    assert TestSchema.__name__ in _SCHEMA_REGISTRY
    assert TestSchema.__name__ in _PIXANO_SCHEMA_REGISTRY

    # Test 3: type cannot be registered twice
    with pytest.raises(
        ValueError,
        match=(
            "Schema <class 'tests.features.schemas.test_registry.test_register_schema_internal.<locals>."
            "TestSchema'> already registered"
        ),
    ):
        _register_schema_internal(TestSchema)

    class NoBaseSchema:
        pass

    # Test 4: type must be a BaseModel
    with pytest.raises(
        ValueError,
        match=(
            "Schema <class 'tests.features.schemas.test_registry.test_register_schema_internal."
            "<locals>.NoBaseSchema'> must be a subclass of BaseSchema"
        ),
    ):
        _register_schema_internal(NoBaseSchema)


def test_register_schema():
    class TestSchema2(BaseSchema):
        pass

    # Test 1: type is not registered
    assert TestSchema2.__name__ not in _SCHEMA_REGISTRY
    assert TestSchema2.__name__ not in _PIXANO_SCHEMA_REGISTRY

    @register_schema
    class TestSchema2(BaseSchema):
        pass

    # Test 2: type is registered
    assert TestSchema2.__name__ in _SCHEMA_REGISTRY
    assert TestSchema2.__name__ not in _PIXANO_SCHEMA_REGISTRY

    # Test 3: type cannot be registered twice
    with pytest.raises(
        ValueError,
        match=(
            "Schema <class 'tests.features.schemas.test_registry.test_register_schema.<locals>."
            "TestSchema2'> already registered"
        ),
    ):

        @register_schema
        class TestSchema2(BaseSchema):
            pass

    class NoBaseSchema2:
        pass

    # Test 4: type must be a BaseModel
    with pytest.raises(
        ValueError,
        match=(
            "Schema <class 'tests.features.schemas.test_registry.test_register_schema.<locals>."
            "NoBaseSchema2'> must be a subclass of BaseSchema"
        ),
    ):
        register_schema(NoBaseSchema2)
