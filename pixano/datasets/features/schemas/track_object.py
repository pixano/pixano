# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.registry import _register_schema_internal

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
