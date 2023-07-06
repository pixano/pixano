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

import pyarrow as pa

from pixano.core.arrow_types.all_pixano_types import createPaType
from pixano.core.arrow_types.bbox import BBox, BBoxType
from pixano.core.arrow_types.compressedRLE import (
    CompressedRLE,
    CompressedRLEArray,
    CompressedRLEType,
    is_compressedRLE_type,
)
from pixano.core.arrow_types.depth_image import (
    DepthImage,
    DepthImageArray,
    DepthImageType,
)
from pixano.core.arrow_types.embedding import (
    Embedding,
    EmbeddingArray,
    EmbeddingType,
    is_embedding_type,
)
from pixano.core.arrow_types.image import Image, ImageArray, ImageType, is_image_type
from pixano.core.arrow_types.objectAnnotation import (
    ObjectAnnotation,
    ObjectAnnotationArray,
    ObjectAnnotationType,
    is_objectAnnotation_type,
)
from pixano.core.arrow_types.pose import Pose, PoseArray, PoseType, is_pose_type
from pixano.core.arrow_types.utils import (
    convert_field,
    fields,
    is_number,
    register_extension_types,
)

__all__ = [
    "BBox",
    "BBoxType",
    "Embedding",
    "EmbeddingType",
    "EmbeddingArray",
    "is_embedding_type",
    "ObjectAnnotation",
    "ObjectAnnotationType",
    "ObjectAnnotationArray",
    "is_objectAnnotation_type",
    "CompressedRLE",
    "CompressedRLEType",
    "CompressedRLEArray",
    "is_compressedRLE_type",
    "Image",
    "ImageType",
    "ImageArray",
    "is_image_type",
    "Pose",
    "PoseType",
    "PoseArray",
    "is_pose_type",
    "DepthImage",
    "DepthImageType",
    "DepthImageArray",
    "convert_field",
    "fields",
    "is_number",
]


arrow_types = [
    PoseType,
    CompressedRLEType,
    EmbeddingType,
    ImageType,
    DepthImageType,
    ObjectAnnotationType,
]

register_extension_types(arrow_types)
