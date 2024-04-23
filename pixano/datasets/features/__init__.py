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

from .schemas.base_schema import BaseSchema
from .schemas.embedding import Embedding
from .schemas.image import Image, is_image
from .schemas.item import Item
from .schemas.object import (
    Object,
    ObjectWithBBox,
    ObjectWithBBoxAndMask,
    ObjectWithMask,
    is_object,
)
from .schemas.point_cloud import PointCloud
from .schemas.registry import register_schema
from .schemas.sequence_frame import SequenceFrame, is_sequence_frame
from .schemas.tracklet import (
    Tracklet,
    TrackletWithTimestamp,
    TrackletWithTimestep,
    TrackletWithTimestepAndTimestamp,
)
from .schemas.video import Video
from .schemas.view import View
from .types.bbox import BBox, is_bbox
from .types.compressed_rle import CompressedRLE
from .types.nd_array_float import NDArrayFloat


__all__ = [
    "BaseSchema",
    "BBox",
    "CompressedRLE",
    "Embedding",
    "Image",
    "Item",
    "Object",
    "ObjectWithBBox",
    "ObjectWithBBoxAndMask",
    "ObjectWithMask",
    "NDArrayFloat",
    "PointCloud",
    "SequenceFrame",
    "Tracklet",
    "TrackletWithTimestamp",
    "TrackletWithTimestep",
    "TrackletWithTimestepAndTimestamp",
    "Video",
    "View",
    "is_bbox",
    "is_image",
    "is_object",
    "is_sequence_frame",
    "register_schema",
]
