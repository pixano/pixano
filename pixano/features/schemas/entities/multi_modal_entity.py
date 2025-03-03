# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..registry import _register_schema_internal
from .named_entity import NamedEntity


@_register_schema_internal
class MultiModalEntity(NamedEntity):
    """A `multimedia` entity.

    A MultiModalEntity represents an entity that is shared among multiple view of different type : image + text.

    Attributes:
        name: The name of the Entity.
    """

    pass


def is_multi_modal_entity(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a `MultiModalEntity` or a subclass of `MultiModalEntity`."""
    return issubclass_strict(cls, MultiModalEntity, strict)


def create_multi_modal_entity(
    name: str,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    parent_ref: EntityRef = EntityRef.none(),
) -> MultiModalEntity:
    """Create a `MultiModalEntity` instance.

    Args:
        name: The name of the multimedia_entity.
        id: MultiModalEntity ID.
        item_ref: Item reference.
        view_ref: View reference.
        parent_ref: Entity reference.

    Returns:
        The created `MultiModalEntity` instance.
    """
    return MultiModalEntity(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        parent_ref=parent_ref,
        name=name,
    )
