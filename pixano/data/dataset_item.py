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

from pydantic import BaseModel


class ItemFeature(BaseModel):
    """Feature

    Attributes:
        name (str): Feature name
        dtype (str): Feature type
        value (str | int | float | bool): Feature value
    """

    name: str
    dtype: str
    value: str | int | float | bool


class ItemURLE(BaseModel):
    """Uncompressed URLE mask type for DatasetItem

    Type for CompressedRLE.to_urle().to_dict()

    Attributes:
        size (list[float]): Mask size
        counts (list[int]): Mask URLE encoding
    """

    size: list[float]
    counts: list[int]


class ItemBBox(BaseModel):
    """BBox type for DatasetItem

    Type for BBox.to_dict()

    Attributes:
        coords (list[float]): List of coordinates in given format
        format (str): Coordinates format, 'xyxy' or 'xywh'
        is_normalized (bool, optional): True if coordinates are normalized to image size
        confidence (float, optional): Bounding box confidence if predicted
    """

    coords: list[float]
    format: str
    is_normalized: Optional[bool] = None
    confidence: Optional[float] = None


class ItemObject(BaseModel):
    """Object type for DatasetItem

    Attributes:
        id (str): Object ID
        item_id (str): Object item ID
        view_id (str): Object view ID
        source_id (str): Object source ID
        bbox (ItemBBox, optional): Object bounding box
        mask (ItemURLE, optional): Object mask
        features (list[ItemFeature], optional): Object features
    """

    id: str
    item_id: str
    view_id: str
    source_id: str
    bbox: Optional[ItemBBox] = None
    mask: Optional[ItemURLE] = None
    features: Optional[list[ItemFeature]] = None


class ItemEmbedding(BaseModel):
    """Embedding type for DatasetItem

    Attributes:
        view_id (str): Embedding view ID
        data (str): Embedding data in base 64
    """

    view_id: str
    data: str


class ItemView(BaseModel):
    """View type for DatasetItem

    Attributes:
        id (str): View ID
        url (str): View URI
        frame_number (int, optional): View frame number
        total_frames (int, optional): View total frames
        features (list[ItemFeature], optional): View features
    """

    id: str
    uri: str
    frame_number: Optional[int] = None
    total_frames: Optional[int] = None
    features: Optional[list[ItemFeature]] = None


class DatasetItem(BaseModel):
    """DatasetItem

    Attributes:
        id (str): Item ID
        features (list[ItemFeature], optional): Item features
        image (list[ItemView], optional): Item image views
        video (list[ItemView], optional): Item video views
        point_cloud (list[ItemView], optional): Item point cloud views
        objects (list[ItemObject], optional): Item objects
    """

    id: str
    features: Optional[list[ItemFeature]] = None
    image: Optional[list[ItemView]] = None
    video: Optional[list[ItemView]] = None
    point_cloud: Optional[list[ItemView]] = None
    objects: Optional[list[ItemObject]] = None
