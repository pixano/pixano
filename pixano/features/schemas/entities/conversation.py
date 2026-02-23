# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ..registry import _register_schema_internal
from .entity import Entity


@_register_schema_internal
class Conversation(Entity):
    """A `Conversation` entity.

    A conversation is an object holding messages ordered by their attribute `number`.
    The Message annotations refer to the conversation via their `entity_id` attribute.

    Attributes:
        kind: Agnostic metadata to store information of the conversation.
    """

    kind: str


def is_conversation(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a `Conversation` or a subclass of `Conversation`."""
    return issubclass_strict(cls, Conversation, strict)


def create_conversation(
    kind: str,
    id: str = "",
    item_id: str = "",
    parent_id: str = "",
) -> Conversation:
    """Create a `Conversation` instance.

    Args:
        kind: Agnostic metadata to store information of the conversation.
        id: Conversation ID.
        item_id: Item ID.
        parent_id: Parent entity ID.

    Returns:
        The created `Conversation` instance.
    """
    return Conversation(
        id=id,
        item_id=item_id,
        parent_id=parent_id,
        kind=kind,
    )
