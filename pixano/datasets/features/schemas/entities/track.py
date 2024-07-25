# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..registry import _register_schema_internal
from .entity import Entity


@_register_schema_internal
class Track(Entity):
    """Track Lance Model.

    Attributes:
        name (str): The name of the track.
    """

    name: str


def is_track(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a Track or a subclass of Track."""
    return issubclass_strict(cls, Track, strict)


def create_track(
    name: str,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    parent_ref: EntityRef = EntityRef.none(),
) -> Track:
    """Create a TrackObject instance.

    Args:
        name (str): The name of the track.
        id (str, optional): Track ID.
        item_ref (ItemRef, optional): Item reference.
        view_ref (ViewRef, optional): View reference.
        parent_ref (EntityRef, optional): Entity reference.

    Returns:
        TrackObject: The created TrackObject instance.
    """
    return Track(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        parent_ref=parent_ref,
        name=name,
    )
