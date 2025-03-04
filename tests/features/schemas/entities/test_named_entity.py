# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import NamedEntity, create_named_entity, is_named_entity
from pixano.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


def test_is_named_entity():
    make_tests_is_sublass_strict(is_named_entity, NamedEntity)


def test_create_track():
    # Test 1: Default references
    named_entity = create_named_entity(
        name="name",
    )

    assert isinstance(named_entity, NamedEntity)
    assert named_entity.name == "name"
    assert named_entity.id == ""
    assert named_entity.item_ref == ItemRef.none()
    assert named_entity.view_ref == ViewRef.none()
    assert named_entity.parent_ref == EntityRef.none()

    # Test 2: Custom references
    named_entity_object = create_named_entity(
        name="name",
        id="id",
        item_ref=ItemRef(id="item_id"),
        view_ref=ViewRef(id="view_id", name="view"),
        parent_ref=EntityRef(id="entity_id", name="entity"),
    )

    assert isinstance(named_entity_object, NamedEntity)
    assert named_entity_object.name == "name"
    assert named_entity_object.id == "id"
    assert named_entity_object.item_ref == ItemRef(id="item_id")
    assert named_entity_object.view_ref == ViewRef(id="view_id", name="view")
    assert named_entity_object.parent_ref == EntityRef(id="entity_id", name="entity")
