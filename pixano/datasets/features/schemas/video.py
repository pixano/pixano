# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info


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
