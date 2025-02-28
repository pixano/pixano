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
class Track(NamedEntity):
    """A `Track` entity.

    A track represents an entity that is shared among multiple view across time.

    Attributes:
        name: The name of the track.
    """

    pass


def is_track(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a `Track` or a subclass of `Track`."""
    return issubclass_strict(cls, Track, strict)


def create_track(
    name: str,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    parent_ref: EntityRef = EntityRef.none(),
) -> Track:
    """Create a `Track` instance.

    Args:
        name: The name of the track.
        id: Track ID.
        item_ref: Item reference.
        view_ref: View reference.
        parent_ref: Entity reference.

    Returns:
        The created `Track` instance.
    """
    return Track(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        parent_ref=parent_ref,
        name=name,
    )
