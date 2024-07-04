# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shortuuid

from pixano.datasets.features.schemas.registry import _register_schema_internal
from pixano.datasets.utils import issubclass_strict

from .base_schema import BaseSchema


@_register_schema_internal
class Tracklet(BaseSchema):
    """Tracklet Lance Model."""

    item_id: str
    track_id: str
    start_timestep: int = -1
    end_timestep: int = -1
    start_timestamp: float = -1.0
    end_timestamp: float = -1.0


def is_tracklet(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of Tracklet."""
    return issubclass_strict(cls, Tracklet, strict)


def create_tracklet(
    item_id: str,
    track_id: str,
    id: str | None = None,
    start_timestep: int = -1,
    end_timestep: int = -1,
    start_timestamp: float = -1.0,
    end_timestamp: float = -1.0,
) -> Tracklet:
    """Create a Tracklet instance.

    Args:
        item_id (str): The item id.
        track_id (str): The track id.
        id (str | None, optional): The tracklet id. If None, a random id is generated.
        start_timestep (int, optional): The start timestep of the tracklet.
        end_timestep (int, optional): The end timestep of the tracklet.
        start_timestamp (float, optional): The start timestamp of the tracklet.
        end_timestamp (float, optional): The end timestamp of the tracklet.

    Returns:
        Tracklet: The created Tracklet instance.
    """
    if start_timestep < -1 or end_timestep < -1 or start_timestamp < -1.0 or end_timestamp < -1.0:
        raise ValueError(
            "start_timestep, end_timestep, start_timestamp, and end_timestamp must be greater than or equal to -1."
        )
    elif start_timestep == -1 and end_timestep == -1 and start_timestamp == -1.0 and end_timestamp == -1.0:
        raise ValueError("At least one of start_timestep, end_timestep, start_timestamp, or end_timestamp must be set.")
    elif start_timestep == -1 and end_timestep > 0:
        raise ValueError("start_timestep must be set if end_timestep is set.")
    elif end_timestep == -1.0 and start_timestep > 0.0:
        raise ValueError("end_timestep must be set if start_timestep is set.")
    elif start_timestamp == -1.0 and end_timestamp > 0.0:
        raise ValueError("start_timestamp must be set if end_timestamp is set.")
    elif end_timestamp == -1.0 and start_timestamp > 0.0:
        raise ValueError("end_timestamp must be set if start_timestamp is set.")
    elif start_timestep > 0 and end_timestep > 0 and start_timestep > end_timestep:
        raise ValueError("start_timestep must be less than or equal to end_timestep.")
    elif start_timestamp > 0 and end_timestamp > 0 and start_timestamp > end_timestamp:
        raise ValueError("start_timestamp must be less than or equal to end_timestamp.")
    return Tracklet(
        id=id if id is not None else shortuuid.uuid(),
        item_id=item_id,
        track_id=track_id,
        start_timestep=start_timestep,
        end_timestep=end_timestep,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )
