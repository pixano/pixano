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


from pixano.core.arrow_types.all_pixano_types import PixanoType, createPaType
from pixano.core.arrow_types.bbox import BBox, BBoxType
from pixano.core.arrow_types.camera import Camera, CameraType
from pixano.core.arrow_types.compressedRLE import CompressedRLE, CompressedRLEType
from pixano.core.arrow_types.depth_image import DepthImage, DepthImageType
from pixano.core.arrow_types.embedding import Embedding, EmbeddingType
from pixano.core.arrow_types.gt_info import GtInfo, GtInfoType
from pixano.core.arrow_types.image import Image, ImageType
from pixano.core.arrow_types.objectAnnotation import (
    ObjectAnnotation,
    ObjectAnnotationType,
)
from pixano.core.arrow_types.pose import Pose, PoseType
from pixano.core.arrow_types.utils import convert_field, fields, is_number

__all__ = [
    "BBox",
    "BBoxType",
    "Embedding",
    "EmbeddingType",
    "ObjectAnnotation",
    "ObjectAnnotationType",
    "CompressedRLE",
    "CompressedRLEType",
    "Image",
    "ImageType",
    "Pose",
    "PoseType",
    "DepthImage",
    "DepthImageType",
    "Camera",
    "CameraType",
    "GtInfo",
    "GtInfoType",
    "PixanoType",
    "createPaType",
    "convert_field",
    "fields",
    "is_number",
]

def is_image_type(field_type):
    return ImageType.equals(field_type)
