# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.registry import _register_schema_internal

from .base_schema import BaseSchema


@_register_schema_internal
class Tracklet(BaseSchema):
    """Tracklet Lance Model."""

    item_id: str
    track_id: str


@_register_schema_internal
class TrackletWithTimestep(Tracklet):
    """Tracklet with Timestep Lance Model."""

    start_timestep: int
    end_timestep: int


@_register_schema_internal
class TrackletWithTimestamp(Tracklet):
    """Tracklet with Timestamp Lance Model."""

    start_timestamp: int  # Note timestamps may be float ?
    end_timestamp: int


@_register_schema_internal
class TrackletWithTimestepAndTimestamp(Tracklet):
    """Tracklet with Timestep and Timestamp Lance Model."""

    start_timestep: int
    end_timestep: int
    start_timestamp: int
    end_timestamp: int


def is_tracklet(cls: type) -> bool:
    """Check if the given class is a subclass of Tracklet."""
    return issubclass(cls, Tracklet)
