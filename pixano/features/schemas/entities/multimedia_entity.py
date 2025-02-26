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
class MultimediaEntity(Entity):
    """A `multimedia` entity.

    A MultimediaEntity represents an entity that is shared among multiple view of different type : image + text.

    Attributes:
        name: The name of the Entity.
    """

    name: str


def is_multimedia_entity(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a `MultimediaEntity` or a subclass of `MultimediaEntity`."""
    return issubclass_strict(cls, MultimediaEntity, strict)


def create_multimedia_entity(
    name: str,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    parent_ref: EntityRef = EntityRef.none(),
) -> MultimediaEntity:
    """Create a `MultimediaEntity` instance.

    Args:
        name: The name of the multimedia_entity.
        id: MultimediaEntity ID.
        item_ref: Item reference.
        view_ref: View reference.
        parent_ref: Entity reference.

    Returns:
        The created `MultimediaEntity` instance.
    """
    return MultimediaEntity(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        parent_ref=parent_ref,
        name=name,
    )
