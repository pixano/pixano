# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import model_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class Tracklet(Annotation):
    """A `Tracklet` is a temporal segment of a video sequence.

    Attributes:
        start_timestep: The start timestep of the tracklet.
        end_timestep: The end timestep of the tracklet.
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
                "start_timestep, end_timestep, start_timestamp, and end_timestamp must be greater than or equal to -1."
            )
        elif (
            self.start_timestep == -1
            and self.end_timestep == -1
            and self.start_timestamp == -1.0
            and self.end_timestamp == -1.0
        ):
            raise ValueError(
                "At least one of start_timestep, end_timestep, start_timestamp, or end_timestamp must be set."
            )
        elif self.start_timestep == -1 and self.end_timestep > 0:
            raise ValueError("start_timestep must be set if end_timestep is set.")
        elif self.end_timestep == -1.0 and self.start_timestep > 0.0:
            raise ValueError("end_timestep must be set if start_timestep is set.")
        elif self.start_timestamp == -1.0 and self.end_timestamp > 0.0:
            raise ValueError("start_timestamp must be set if end_timestamp is set.")
        elif self.end_timestamp == -1.0 and self.start_timestamp > 0.0:
            raise ValueError("end_timestamp must be set if start_timestamp is set.")
        elif self.start_timestep > 0 and self.end_timestep > 0 and self.start_timestep > self.end_timestep:
            raise ValueError("start_timestep must be less than or equal to end_timestep.")
        elif self.start_timestamp > 0 and self.end_timestamp > 0 and self.start_timestamp > self.end_timestamp:
            raise ValueError("start_timestamp must be less than or equal to end_timestamp.")
        return self


def is_tracklet(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `Tracklet`."""
    return issubclass_strict(cls, Tracklet, strict)


def create_tracklet(
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
    start_timestep: int = -1,
    end_timestep: int = -1,
    start_timestamp: float = -1.0,
    end_timestamp: float = -1.0,
) -> Tracklet:
    """Create a `Tracklet` instance.

    Args:
        id: The tracklet id.
        item_ref: The item reference.
        view_ref: The view reference.
        entity_ref: The parent track reference.
        source_ref: The source reference.
        start_timestep: The start timestep of the tracklet.
        end_timestep: The end timestep of the tracklet.
        start_timestamp: The start timestamp of the tracklet.
        end_timestamp: The end timestamp of the tracklet.

    Returns:
        The created `Tracklet` instance.
    """
    return Tracklet(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
        start_timestep=start_timestep,
        end_timestep=end_timestep,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )
