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

from .image import CompressedRLEType


class BBoxType(pa.ExtensionType):
    """Bounding box type as PyArrow list of PyArrow float32"""

    def __init__(self):
        super(BBoxType, self).__init__(pa.list_(pa.float32(), list_size=4), "bbox")

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return BBoxType()

    def __arrow_ext_serialize__(self):
        return b""


class EmbeddingType(pa.ExtensionType):
    """Embedding type as PyArrow binary"""

    def __init__(self):
        super(EmbeddingType, self).__init__(pa.binary(), "embedding")

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return EmbeddingType()

    def __arrow_ext_serialize__(self):
        return b""


class Embedding(BaseModel):
    """Embedding class

    Attributes:
        embedding (bytes): Embedding as binary
    """

    embedding: bytes


class ObjectAnnotation(BaseModel):
    """ObjectAnnotation class to contain all annotation data

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

    # Object ID and View ID
    id: str
    view_id: Optional[str] = None
    # Bounding Box
    bbox: Optional[list[float]] = [0.0] * 4
    bbox_source: Optional[str] = None
    bbox_confidence: Optional[float] = None
    is_group_of: Optional[bool] = None
    is_difficult: Optional[bool] = None
    is_truncated: Optional[bool] = None
    # Mask
    mask: Optional[dict] = None
    mask_source: Optional[str] = None
    area: Optional[float] = None
    # 6D Poses
    pose: Optional[dict[str, list[float]]] = {
        "cam_R_m2c": [0.0] * 9,
        "cam_t_m2c": [0.0] * 3,
    }
    # Category
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    identity: Optional[str] = None


def ObjectAnnotationType() -> pa.StructType:
    """ObjectAnnotation type as PyArrow StructType

    Returns:
        pa.StructType: ObjectAnnotation StructType
    """

    pose_schema = pa.struct(
        [
            pa.field("cam_R_m2c", pa.list_(pa.float64(), list_size=9)),
            pa.field("cam_t_m2c", pa.list_(pa.float64(), list_size=3)),
        ]
    )

    return pa.struct(
        [
            # Object ID and View ID
            pa.field("id", pa.string()),
            pa.field("view_id", pa.string(), nullable=True),
            # Bounding Box
            pa.field("bbox", BBoxType(), nullable=True),
            pa.field("bbox_source", pa.string(), nullable=True),
            pa.field("bbox_confidence", pa.float32(), nullable=True),
            pa.field("is_group_of", pa.bool_(), nullable=True),
            pa.field("is_difficult", pa.bool_(), nullable=True),
            pa.field("is_truncated", pa.bool_(), nullable=True),
            # Mask
            pa.field("mask", CompressedRLEType(), nullable=True),
            pa.field("mask_source", pa.string(), nullable=True),
            pa.field("area", pa.float32(), nullable=True),
            # 6D Poses
            pa.field("pose", pose_schema, nullable=True),
            # Category
            pa.field("category_id", pa.int32(), nullable=True),
            pa.field("category_name", pa.string(), nullable=True),
            pa.field("identity", pa.string(), nullable=True),
        ]
    )


def is_embedding_type(t: pa.DataType) -> bool:
    """Returns True if value is an instance of EmbeddingType

    Args:
        t (pa.DataType): Value to check

    Returns:
        bool: Type checking response
    """
    return isinstance(t, EmbeddingType)
