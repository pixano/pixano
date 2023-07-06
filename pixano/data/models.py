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

from typing import Any, Optional

from pydantic import BaseModel


class Point2d(BaseModel):
    """Point2d

    Attributes:
        x (float): x coordinate
        y (float): y coordinate
    """

    x: float
    y: float


class Rectangle(BaseModel):
    """Rectangle

    Attributes:
        bottom_left (Point2d): bottom-left corner of the rectangle
        width (float): width of the rectangle
        height (float): height of the rectangle
    """

    bottom_left: Point2d
    width: float
    height: float


class Polygon(BaseModel):
    """Polygon

    Attributes:
        points (list[Point2d]): Polygon points list
    """

    points: list[Point2d]


MultiPolygon = list[Polygon]


class Point3d(BaseModel):
    """Point3d structure

    Attributes:
        x (float): x coordinate
        y (float): y coordinate
        z (float): z coordinate
    """

    x: float
    y: float
    z: float


class Mask(BaseModel):
    pass


class RLE(BaseModel):
    """RLE Mask (Run Length Encoding)

    Attributes:
        size (list[int]): Image size (width, height)
        counts (bytes): RLE Mask
    """

    size: list[int]
    counts: bytes


class Category(BaseModel):
    """Category

    Attributes:
        name (str): Category name
        id (int, optional): Category ID
    """

    name: str
    id: Optional[int]


class ObjectAnnotation(BaseModel):
    """ObjectAnnotation

    Attributes:
        id (str): Annotation unique ID
        view_id (str, optional): View ID (e.g. 'image', 'cam_2')
        bbox (list[float], optional): Bounding box coordinates in xywh format (using top left point as reference)
        bbox_source (str, optional): Bounding box source
        bbox_confidence (float, optional): Bounding box confidence
        is_group_of (bool, optional): is_group_of
        is_difficult (bool, optional): is_difficult
        is_truncated (bool, optional): is_truncated
        mask (RLE, optional): Mask
        mask_source (str, optional): Mask source
        area (float, optional): area
        pose (dict[str, list[float]], optional): Pose
        category_id (int, optional): Category ID
        category_name (str, optional): Category name
        identity (str, optional): Identity
    """

    id: str
    view_id: Optional[str] = None
    bbox: Optional[list[float]] = None
    bbox_source: Optional[str] = None
    bbox_confidence: Optional[float] = None
    is_group_of: Optional[bool] = None
    is_difficult: Optional[bool] = None
    is_truncated: Optional[bool] = None
    mask: Optional[RLE] = None
    mask_source: Optional[str] = None
    area: Optional[float] = None
    pose: Optional[dict[str, list[float]]] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    identity: Optional[str] = None


class Feature(BaseModel):
    """Feature

    Attributes:
        name (str): Feature name
        dtype (str): Feature dtype
        value (Any): Feature value
    """

    name: str
    dtype: str
    value: Any


Features = list[Feature]


class DatasetSpec(BaseModel):
    """DatasetSpec

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        num_elements (int): Number of elements in dataset
        preview (str): Dataset preview
        splits (dict[str, int], optional): Dataset splits
        category_index (dict[str, int], optional): Dataset category index
    """

    id: str
    name: str
    description: str
    num_elements: int
    preview: str
    splits: Optional[dict[str, int]] = None
    category_index: Optional[dict[str, int]] = None
