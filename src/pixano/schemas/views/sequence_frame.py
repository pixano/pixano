# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pathlib import Path

from pixano.utils import issubclass_strict

from .image import Image, create_image


class SequenceFrame(Image):
    """Sequence of image. Used to store video frames.

    Attributes:
        timestamp: The timestamp of the frame.
        frame_index: The index of the frame in the sequence.
    """

    timestamp: float
    frame_index: int


def is_sequence_frame(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `SequenceFrame`."""
    return issubclass_strict(cls, SequenceFrame, strict)

