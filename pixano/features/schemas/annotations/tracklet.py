# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import model_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict

from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class Tracklet(Annotation):
    """A `Tracklet` is a temporal segment of a video sequence.

    Attributes:
        start_frame: The start frame of the tracklet.
        end_frame: The end frame of the tracklet.
        start_timestamp: The start timestamp of the tracklet.
        end_timestamp: The end timestamp of the tracklet.
    """

    start_frame: int = -1
    end_frame: int = -1
    start_timestamp: float = -1.0
    end_timestamp: float = -1.0

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if (
            self.start_frame < -1
            or self.end_frame < -1
            or self.start_timestamp < -1.0
            or self.end_timestamp < -1.0
        ):
            raise ValueError(
                "start_frame, end_frame, start_timestamp, and end_timestamp must be greater than or equal to -1."
            )
        elif (
            self.start_frame == -1
            and self.end_frame == -1
            and self.start_timestamp == -1.0
            and self.end_timestamp == -1.0
        ):
            raise ValueError(
                "At least one of start_frame, end_frame, start_timestamp, or end_timestamp must be set."
            )
        elif self.start_frame == -1 and self.end_frame > 0:
            raise ValueError("start_frame must be set if end_frame is set.")
        elif self.end_frame == -1 and self.start_frame > 0:
            raise ValueError("end_frame must be set if start_frame is set.")
        elif self.start_timestamp == -1.0 and self.end_timestamp > 0.0:
            raise ValueError("start_timestamp must be set if end_timestamp is set.")
        elif self.end_timestamp == -1.0 and self.start_timestamp > 0.0:
            raise ValueError("end_timestamp must be set if start_timestamp is set.")
        elif self.start_frame > 0 and self.end_frame > 0 and self.start_frame > self.end_frame:
            raise ValueError("start_frame must be less than or equal to end_frame.")
        elif self.start_timestamp > 0 and self.end_timestamp > 0 and self.start_timestamp > self.end_timestamp:
            raise ValueError("start_timestamp must be less than or equal to end_timestamp.")
        return self


def is_tracklet(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `Tracklet`."""
    return issubclass_strict(cls, Tracklet, strict)


def create_tracklet(
    id: str = "",
    item_id: str = "",
    view_name: str = "",
    entity_id: str = "",
    source_id: str = "",
    start_frame: int = -1,
    end_frame: int = -1,
    start_timestamp: float = -1.0,
    end_timestamp: float = -1.0,
) -> Tracklet:
    """Create a `Tracklet` instance.

    Args:
        id: The tracklet id.
        item_id: The item ID.
        view_name: The view name.
        entity_id: The parent entity ID.
        source_id: The source ID.
        start_frame: The start frame of the tracklet.
        end_frame: The end frame of the tracklet.
        start_timestamp: The start timestamp of the tracklet.
        end_timestamp: The end timestamp of the tracklet.

    Returns:
        The created `Tracklet` instance.
    """
    return Tracklet(
        id=id,
        item_id=item_id,
        view_name=view_name,
        entity_id=entity_id,
        source_id=source_id,
        start_frame=start_frame,
        end_frame=end_frame,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )
