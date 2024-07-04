# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shortuuid

from pixano.datasets.features.schemas.registry import _register_schema_internal
from pixano.datasets.utils import issubclass_strict

from .object import Object


@_register_schema_internal
class TrackObject(Object):
    """Object belonging to a track.

    Attributes:
        tracklet_id (str): tracklet id
        is_key (bbol): True if object is a "key"
        frame_idx (int): frame index
    """

    tracklet_id: str
    is_key: bool
    frame_idx: int


def is_track_object(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a TrackObject or a subclass of TrackObject."""
    return issubclass_strict(cls, TrackObject, strict)


def create_track_object(
    item_id: str,
    view_id: str,
    tracklet_id: str,
    is_key: bool,
    frame_idx: int,
    id: str | None = None,
) -> TrackObject:
    """Create a TrackObject instance.

    Args:
        item_id (str): The item id.
        view_id (str): The view id.
        tracklet_id (str): The tracklet id.
        is_key (bool): True if object is a "key".
        frame_idx (int): The frame index.
        id (str | None, optional): The object id. If None, a random id is generated.

    Returns:
        TrackObject: The created TrackObject instance.
    """
    return TrackObject(
        id=id if id is not None else shortuuid.uuid(),
        item_id=item_id,
        view_id=view_id,
        tracklet_id=tracklet_id,
        is_key=is_key,
        frame_idx=frame_idx,
    )
