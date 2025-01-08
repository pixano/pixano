# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .entity import Entity


@_register_schema_internal
class Conversation(Entity):
    """A `Conversation` entity.

    A conversation is an object refered by Message annotations via their `entity_ref` attribute.

    Attributes:
        kind: Agnostic metadata to store information of the conversation.
        with_model: Model source reference, or may refer to the groundtruth source.
    """

    kind: str
    with_model: SourceRef


def is_conversation(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a `Conversation` or a subclass of `Conversation`."""
    return issubclass_strict(cls, Conversation, strict)


def create_conversation(
    kind: str,
    with_model: SourceRef = SourceRef.none(),
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    parent_ref: EntityRef = EntityRef.none(),
) -> Conversation:
    """Create a `Conversation` instance.

    Args:
        kind: Agnostic metadata to store information of the conversation.
        with_model: Model source reference, or may refer to the groundtruth source.
        id: Conversation ID.
        item_ref: Item reference.
        view_ref: View reference.
        parent_ref: Entity reference.

    Returns:
        The created `Conversation` instance.
    """
    return Conversation(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        parent_ref=parent_ref,
        kind=kind,
        with_model=with_model,
    )
