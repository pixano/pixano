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

    Args:
        x (float): x coordinate
        y (float): y coordinate
    """

    x: float
    y: float


class Rectangle(BaseModel):
    """Rectangle

    Args:
        bottom_left (Point2d): bottom-left corner of the rectangle
        width (float): width of the rectangle
        height (float): height of the rectangle
    """

    bottom_left: Point2d
    width: float
    height: float


class Polygon(BaseModel):
    """Polygon

    Args:
        points (list[Point2d]): polygon points list
    """

    points: list[int] | list[Point2d]


MultiPolygon = list[Polygon]


class Point3d(BaseModel):
    """Point3d structure

    Args:
        x (float): x coordinate
        y (float): y coordinate
        z (float): z coordinate
    """


class Mask(BaseModel):
    pass


class RLE(BaseModel):
    """RLE mask - Run Length Encoding

    Args:
        counts (list[int] | str): "Run length Encoding" mask
        size (list[int]): size of the image (width, height)
    """

    size: list[int]
    counts: bytes


class Category(BaseModel):
    """Category

    Args:
        id (int | None): category id
        name (str): category name
    """

    id: int | None
    name: str


class ObjectAnnotation(BaseModel):
    id: str
    view_id: Optional[str] = None
    bbox: Optional[list[float]] = None
    bbox_source: Optional[str] = None
    is_group_of: Optional[bool] = None
    is_difficult: Optional[bool] = None
    is_truncated: Optional[bool] = None
    area: Optional[float] = None
    mask: Optional[RLE] = None
    mask_source: Optional[str] = None
    identity: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    pose: Optional[dict[str, list[float]]] = None


class Feature(BaseModel):
    dtype: str
    name: str
    value: Any


Features = list[Feature]


class DatasetSpec(BaseModel):
    id: str
    name: str
    description: str
    num_elements: int
    preview: str
    splits: Optional[dict[str, int]] = None
    category_index: Optional[dict[str, int]] = None
