# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .base_schema import BaseSchema
from .embedding import Embedding
from .group import _SchemaGroup
from .image import Image, create_image, is_image
from .image_object import ImageObject, create_image_object, is_image_object
from .item import Item, is_item
from .object import Object, is_object
from .point_cloud import PointCloud, create_point_cloud, is_point_cloud
from .registry import register_schema
from .sequence_frame import SequenceFrame, create_sequence_frame, is_sequence_frame
from .track_object import TrackObject, create_track_object, is_track_object
from .tracklet import Tracklet, create_tracklet, is_tracklet
from .video import Video, create_video, is_video
from .view import View, is_view


__all__ = [
    "BaseSchema",
    "Embedding",
    "Image",
    "ImageObject",
    "Item",
    "Object",
    "PointCloud",
    "SequenceFrame",
    "Tracklet",
    "TrackObject",
    "Video",
    "View",
    "_SchemaGroup",
    "create_image",
    "create_image_object",
    "create_point_cloud",
    "create_sequence_frame",
    "create_track_object",
    "create_tracklet",
    "create_video",
    "is_image_object",
    "is_image",
    "is_item",
    "is_object",
    "is_point_cloud",
    "is_sequence_frame",
    "is_track_object",
    "is_tracklet",
    "is_video",
    "is_view",
    "register_schema",
]
