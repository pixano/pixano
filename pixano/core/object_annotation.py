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

from typing import Optional

import pyarrow as pa
from pydantic import BaseModel

from pixano.core.bbox import BBox, BBoxType
from pixano.core.compressed_rle import CompressedRLE, CompressedRLEType
from pixano.core.pixano_type import PixanoType, create_pyarrow_type
from pixano.core.pose import Pose, PoseType


class ObjectAnnotation(PixanoType, BaseModel):
    """ObjectAnnotation type using all annotation data

    Attributes:
        id (str): Annotation unique ID
        view_id (str, optional): View ID (e.g. 'image', 'cam_2')
        bbox (list[float], optional): Bounding box coordinates in xywh format (using top left point as reference)
        bbox_source (str, optional): Bounding box source
        bbox_confidence (float, optional): Bounding box confidence
        is_group_of (bool, optional): is_group_of
        is_difficult (bool, optional): is_difficult
        is_truncated (bool, optional): is_truncated
        mask (dict[str, bytes], optional): Mask
        mask_source (str, optional): Mask source
        area (float, optional): area
        pose (dict[str, list[float]], optional): Pose
        category_id (int, optional): Category ID
        category_name (str, optional): Category name
        identity (str, optional): Identity
    """

    id: str
    view_id: Optional[str] = None
    bbox: Optional[BBox] = BBox.from_xywh([0, 0, 0, 0])
    bbox_source: Optional[str] = None
    bbox_confidence: Optional[float] = None
    is_group_of: Optional[bool] = None
    is_difficult: Optional[bool] = None
    is_truncated: Optional[bool] = None
    mask: Optional[CompressedRLE] = CompressedRLE([0, 0], b"")
    mask_source: Optional[str] = None
    area: Optional[float] = None
    pose: Optional[Pose] = Pose([0.0] * 9, [0.0] * 3)
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    identity: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    @staticmethod
    def to_struct() -> pa.StructType:
        """Return ObjectAnnotation type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        return pa.struct(
            [
                pa.field("id", pa.string()),
                pa.field("view_id", pa.string(), nullable=True),
                pa.field("bbox", BBoxType, nullable=True),
                pa.field("bbox_source", pa.string(), nullable=True),
                pa.field("bbox_confidence", pa.float32(), nullable=True),
                pa.field("is_group_of", pa.bool_(), nullable=True),
                pa.field("is_difficult", pa.bool_(), nullable=True),
                pa.field("is_truncated", pa.bool_(), nullable=True),
                pa.field("mask", CompressedRLEType, nullable=True),
                pa.field("mask_source", pa.string(), nullable=True),
                pa.field("area", pa.float32(), nullable=True),
                pa.field("pose", PoseType, nullable=True),
                pa.field("category_id", pa.int32(), nullable=True),
                pa.field("category_name", pa.string(), nullable=True),
                pa.field("identity", pa.string(), nullable=True),
            ]
        )


ObjectAnnotationType = create_pyarrow_type(
    ObjectAnnotation.to_struct(), "ObjectAnnotation", ObjectAnnotation
)
