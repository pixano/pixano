# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

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
    item_id: str = "",
    parent_id: str = "",
) -> MultiModalEntity:
    """Create a `MultiModalEntity` instance.

    Args:
        name: The name of the multimedia_entity.
        id: MultiModalEntity ID.
        item_id: Item ID.
        parent_id: Parent entity ID.

    Returns:
        The created `MultiModalEntity` instance.
    """
    return MultiModalEntity(
        id=id,
        item_id=item_id,
        parent_id=parent_id,
        name=name,
    )
