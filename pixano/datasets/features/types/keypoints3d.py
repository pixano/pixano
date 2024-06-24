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
class KeyPoints3D(pydantic.BaseModel):
    """A set of 3D keypoints.

    Attributes:
        template_id (str): id of keypoint template
        coords (list[float]): List of 3D coordinates of the keypoints.
        # edges (list[list[int]]): List of edges between keypoints.
        visibles (list[bool]): List of visibility status for each keypoint.
    """
    template_id: str
    coords: list[float]
    # edges: list[list[int]]
    visibles: list[bool]   # replace by features: list[dict] ?

    @staticmethod
    def none():
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value

        Returns:
            KeyPoints3D: "None" KeyPoints3D
        """
        return KeyPoints3D(template_id="None", coords=[0, 0, 0], visibles=[False])


def is_keypoints3d(cls: type) -> bool:
    """Check if a class is a subclass of Keypoints3D.

    Parameters:
        cls (type): The class to check.

    Returns:
        bool: True if the class is a subclass of KeyPoints3D, False otherwise.
    """
    return issubclass(cls, KeyPoints3D)
