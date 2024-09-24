# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime, timedelta

import pytest

from pixano.utils.validation import issubclass_strict, validate_and_init_create_at_and_update_at


def test_issubclass_strict():
    class Class_:
        pass

    class SubClass(Class_):
        pass

    assert issubclass_strict(SubClass, Class_, strict=False)
    assert not issubclass_strict(SubClass, Class_, strict=True)

    assert issubclass_strict(Class_, Class_, strict=False)
    assert issubclass_strict(Class_, Class_, strict=True)


def test_validate_and_init_create_at_and_update_at():
    now = datetime.now()

    # Test when both created_at and updated_at are None
    created_at, updated_at = validate_and_init_create_at_and_update_at(None, None)
    assert isinstance(created_at, datetime)
    assert isinstance(updated_at, datetime)
    assert created_at == updated_at

    # Test when created_at is provided and updated_at is None
    created_at = now - timedelta(days=1)
    updated_at = None
    new_created_at, new_updated_at = validate_and_init_create_at_and_update_at(created_at, updated_at)
    assert new_created_at == created_at
    assert new_updated_at == created_at

    # Test when both created_at and updated_at are provided and valid
    created_at = now - timedelta(days=2)
    updated_at = now - timedelta(days=1)
    new_created_at, new_updated_at = validate_and_init_create_at_and_update_at(created_at, updated_at)
    assert new_created_at == created_at
    assert new_updated_at == updated_at

    # Test when created_at and updated_at are provided as strings
    created_at = (now - timedelta(days=2)).isoformat()
    updated_at = (now - timedelta(days=1)).isoformat()
    new_created_at, new_updated_at = validate_and_init_create_at_and_update_at(created_at, updated_at)
    assert new_created_at == datetime.fromisoformat(created_at)
    assert new_updated_at == datetime.fromisoformat(updated_at)

    # Test when updated_at is provided but created_at is None
    with pytest.raises(ValueError, match="created_at should be set if updated_at is set."):
        validate_and_init_create_at_and_update_at(None, now)

    # Test when updated_at is earlier than created_at
    created_at = now
    updated_at = now - timedelta(days=1)
    with pytest.raises(ValueError, match="updated_at should be greater than created_at."):
        validate_and_init_create_at_and_update_at(created_at, updated_at)

    # Test when created_at is not a datetime object
    with pytest.raises(ValueError, match="created_at should be a datetime object or None."):
        validate_and_init_create_at_and_update_at(1, None)

    # Test when updated_at is not a datetime object
    with pytest.raises(ValueError, match="updated_at should be a datetime object or None."):
        validate_and_init_create_at_and_update_at(now, 1)
