# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from .image import Image
from .registry import _register_schema_internal


@_register_schema_internal
class SequenceFrame(Image):
    """Sequence Frame Lance Model."""

    sequence_id: str
    timestamp: float
    frame_index: int


def is_sequence_frame(cls: type) -> bool:
    """Check if the given class is a subclass of Sequence."""
    return issubclass(cls, SequenceFrame)
