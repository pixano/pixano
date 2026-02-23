# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ..registry import _register_schema_internal
from .entity import Entity


@_register_schema_internal
class NamedEntity(Entity):
    """A named entity.

    A NamedEntity represents an entity with a simple name attribute.

    Attributes:
        name: The name of the entity.
    """

    name: str


def is_named_entity(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a `NamedEntity` or a subclass of `NamedEntity`."""
    return issubclass_strict(cls, NamedEntity, strict)


def create_named_entity(
    name: str,
    id: str = "",
    item_id: str = "",
    parent_id: str = "",
) -> NamedEntity:
    """Create a `NamedEntity` instance.

    Args:
        name: The name of the entity.
        id: NamedEntity ID.
        item_id: Item ID.
        parent_id: Parent entity ID.

    Returns:
        The created `NamedEntity` instance.
    """
    return NamedEntity(
        id=id,
        item_id=item_id,
        parent_id=parent_id,
        name=name,
    )
