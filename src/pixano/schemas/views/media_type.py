# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The kinds of media a dataset's records are made of.

A record may hold several media of several types — a nuScenes record has six camera images and
a point cloud. This is the vocabulary a user chooses from when a job should cover some of them,
and the one the embeddings health counts in: one definition, so that the worker and the
application never disagree on what an image is.
"""

from typing import Literal, get_args

from .image import is_image
from .point_cloud import is_point_cloud
from .sequence_frame import is_sequence_frame
from .text import is_text
from .video import is_video


MediaType = Literal["image", "video", "point_cloud", "text"]
MEDIA_TYPES: tuple[str, ...] = get_args(MediaType)


def media_type_of(schema: type) -> str | None:
    """The media type a table's schema holds, or None for a table that holds no media.

    A frame of a video is an image to the schemas (`SequenceFrame` derives from `Image`), but it
    belongs to its video: choosing images on a video dataset must not cover every frame.
    """
    if is_sequence_frame(schema) or is_video(schema):
        return "video"
    if is_image(schema):
        return "image"
    if is_point_cloud(schema):
        return "point_cloud"
    if is_text(schema):
        return "text"
    return None
