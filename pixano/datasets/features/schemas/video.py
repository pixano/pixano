# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .registry import _register_schema_internal
from .view import View


@_register_schema_internal
class Video(View):
    """Video Lance Model."""

    url: str
    num_frames: int
    fps: float
    width: int
    height: int
    format: str
    duration: float


def is_video(cls: type) -> bool:
    """Check if the given class is a subclass of Video."""
    return issubclass(cls, Video)
