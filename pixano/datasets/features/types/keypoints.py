# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2024)
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

import pydantic

from .registry import _register_type_internal


@_register_type_internal
class KeyPoints(pydantic.BaseModel):
    """A set of keypoints.

    Attributes:
        template_id (str): id of keypoint template
        coords (list[float]): List of 2D coordinates of the keypoints.
        # edges (list[list[int]]): List of edges between keypoints.
        visibles (list[bool]): List of visibility status for each keypoint.
    """

    template_id: str
    coords: list[float]
    # edges: list[list[int]]
    visibles: list[bool]

    @staticmethod
    def none():
        return KeyPoints(template_id="None", coords=[0, 0], visibles=[False])
