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

from typing import Any, List, Mapping, Optional

from pydantic import BaseModel


class ObjectAnnotation(BaseModel):
    """Object Annotation class to contain all annotation data

    Args:
        id (str): Annotation unique ID
        view_id (str, optional): View ID (e.g. 'image', 'cam_2')
        bbox (list[float], optional): Bounding box coordinates in xywh format (using top left point as reference)
        bbox_source (str, optional): Bounding box source
        bbox_confidence (float, optional): Bounding box confidence
        is_group_of (bool, optional): is_group_of
        is_difficult (bool, optional): is_difficult
        is_truncated (bool, optional): is_truncated
        area (float, optional): area
        mask (Mapping[str, Any], optional): Mask
        mask_source (str, optional): Mask source
        identity (str, optional): Identity
        category_id (int, optional): Category ID
        category_name (str, optional): Category name
        pose (Mapping, optional): Pose
    """
    # Have to be consistent with function ObjectAnnotationType (pixano>core>arrow_types>__init__.py)
    id: str
    view_id: Optional[str] = None
    bbox: Optional[list[float]] = None
    bbox_source: Optional[str] = None
    bbox_confidence: Optional[float] = None
    is_group_of: Optional[bool] = None
    is_difficult: Optional[bool] = None
    is_truncated: Optional[bool] = None
    area: Optional[float] = None
    mask: Optional[Mapping[str, Any]] = None
    mask_source: Optional[str] = None
    identity: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    pose: Optional[Mapping[str, List[float]]] = {
        "cam_R_m2c": [0] * 9,
        "cam_t_m2c": [0] * 3,
    }
