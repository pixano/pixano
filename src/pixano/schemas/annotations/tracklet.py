# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pydantic import model_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict

from .entity_annotation import EntityAnnotation


class Tracklet(EntityAnnotation):
    """A Tracklet is a temporal segment representing the trajectory of an entity across a video sequence.

    Attributes:
        start_frame: The start frame of the tracklet.
        end_frame: The end frame of the tracklet.
        start_timestamp: The start timestamp of the tracklet.
        end_timestamp: The end timestamp of the tracklet.
    """
    start_timestep: int = -1
    end_timestep: int = -1
    start_timestamp: float = -1.0
    end_timestamp: float = -1.0

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if (
            self.start_timestep < -1
            or self.end_timestep < -1
            or self.start_timestamp < -1.0
            or self.end_timestamp < -1.0
        ):
            raise ValueError(
                "start_frame, end_frame, start_timestamp, and end_timestamp must be greater than or equal to -1."
            )
        has_frames = self.start_timestep != -1 or self.end_timestep != -1
        has_timestamps = self.start_timestamp != -1.0 or self.end_timestamp != -1.0
        if has_frames:
            if self.start_timestep == -1:
                raise ValueError("start_frame must be set if end_frame is set.")
            if self.end_timestep == -1:
                raise ValueError("end_frame must be set if start_frame is set.")
            if self.start_timestep > self.end_timestep:
                raise ValueError("start_frame must be less than or equal to end_frame.")
        if has_timestamps:
            if self.start_timestamp == -1.0:
                raise ValueError("start_timestamp must be set if end_timestamp is set.")
            if self.end_timestamp == -1.0:
                raise ValueError("end_timestamp must be set if start_timestamp is set.")
            if self.start_timestamp > self.end_timestamp:
                raise ValueError("start_timestamp must be less than or equal to end_timestamp.")
        return self

def is_tracklet(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a Tracklet or subclass of Tracklet."""
    return issubclass_strict(cls, Tracklet, strict)