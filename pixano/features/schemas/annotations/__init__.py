# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .annotation import Annotation, is_annotation
from .bbox import BBox, BBox3D, create_bbox, create_bbox3d, is_bbox, is_bbox3d
from .camcalibration import (
    BaseIntrinsics,
    CamCalibration,
    Extrinsics,
    Intrinsics,
    create_cam_calibration,
    is_cam_calibration,
)
from .classification import Classification, create_classification, is_classification
from .compressed_rle import CompressedRLE, create_compressed_rle, is_compressed_rle
from .info_extraction import NamedEntity, Relation, create_named_entity, create_relation, is_named_entity, is_relation
from .keypoints import KeyPoints, KeyPoints3D, create_keypoints, create_keypoints3d, is_keypoints, is_keypoints3d
from .tracklet import Tracklet, create_tracklet, is_tracklet


__all__ = [
    "Annotation",
    "BaseIntrinsics",
    "BBox",
    "BBox3D",
    "CamCalibration",
    "Classification",
    "CompressedRLE",
    "Extrinsics",
    "Intrinsics",
    "KeyPoints",
    "KeyPoints3D",
    "NamedEntity",
    "Tracklet",
    "Relation",
    "is_annotation",
    "is_bbox",
    "is_bbox3d",
    "is_cam_calibration",
    "is_classification",
    "is_compressed_rle",
    "is_keypoints",
    "is_keypoints3d",
    "is_named_entity",
    "is_tracklet",
    "is_relation",
    "create_bbox",
    "create_bbox3d",
    "create_cam_calibration",
    "create_classification",
    "create_compressed_rle",
    "create_keypoints",
    "create_keypoints3d",
    "create_named_entity",
    "create_tracklet",
    "create_relation",
]
