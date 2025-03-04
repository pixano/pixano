# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
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
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    parent_ref: EntityRef = EntityRef.none(),
) -> NamedEntity:
    """Create a `NamedEntity` instance.

    Args:
        name: The name of the entity.
        id: NamedEntity ID.
        item_ref: Item reference.
        view_ref: View reference.
        parent_ref: Entity reference.

    Returns:
        The created `NamedEntity` instance.
    """
    return NamedEntity(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        parent_ref=parent_ref,
        name=name,
    )
