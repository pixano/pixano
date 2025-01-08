# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import Conversation, create_conversation, is_conversation
from pixano.features.types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


def test_is_conversation():
    make_tests_is_sublass_strict(is_conversation, Conversation)


def test_create_conversation():
    # Test 1: Default references
    conversation = create_conversation(
        kind="question",
        with_model=SourceRef(id="source_id", name="source"),
    )

    assert isinstance(conversation, Conversation)
    assert conversation.kind == "question"
    assert conversation.id == ""
    assert conversation.with_model == SourceRef(id="source_id", name="source")
    assert conversation.item_ref == ItemRef.none()
    assert conversation.view_ref == ViewRef.none()
    assert conversation.parent_ref == EntityRef.none()

    # Test 2: Custom references
    conversation_object = create_conversation(
        kind="name",
        id="id",
        item_ref=ItemRef(id="item_id"),
        view_ref=ViewRef(id="view_id", name="view"),
        parent_ref=EntityRef(id="entity_id", name="entity"),
        with_model=SourceRef(id="source_id", name="source"),
    )

    assert isinstance(conversation_object, Conversation)
    assert conversation_object.kind == "name"
    assert conversation_object.id == "id"
    assert conversation_object.item_ref == ItemRef(id="item_id")
    assert conversation_object.view_ref == ViewRef(id="view_id", name="view")
    assert conversation_object.parent_ref == EntityRef(id="entity_id", name="entity")
    assert conversation_object.with_model == SourceRef(id="source_id", name="source")
