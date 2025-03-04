# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import MultiModalEntity, create_multi_modal_entity, is_multi_modal_entity
from pixano.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


def test_is_multimedia_entity():
    make_tests_is_sublass_strict(is_multi_modal_entity, MultiModalEntity)


def test_create_track():
    # Test 1: Default references
    multimodal_entity = create_multi_modal_entity(
        name="name",
    )

    assert isinstance(multimodal_entity, MultiModalEntity)
    assert multimodal_entity.name == "name"
    assert multimodal_entity.id == ""
    assert multimodal_entity.item_ref == ItemRef.none()
    assert multimodal_entity.view_ref == ViewRef.none()
    assert multimodal_entity.parent_ref == EntityRef.none()

    # Test 2: Custom references
    multimodal_entity_object = create_multi_modal_entity(
        name="name",
        id="id",
        item_ref=ItemRef(id="item_id"),
        view_ref=ViewRef(id="view_id", name="view"),
        parent_ref=EntityRef(id="entity_id", name="entity"),
    )

    assert isinstance(multimodal_entity_object, MultiModalEntity)
    assert multimodal_entity_object.name == "name"
    assert multimodal_entity_object.id == "id"
    assert multimodal_entity_object.item_ref == ItemRef(id="item_id")
    assert multimodal_entity_object.view_ref == ViewRef(id="view_id", name="view")
    assert multimodal_entity_object.parent_ref == EntityRef(id="entity_id", name="entity")
