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
        states (list[str]): Status for each keypoint. ("visible", "invisible", "hidden")
    """

    template_id: str
    coords: list[float]
    states: list[str]  # replace by features: list[dict] ?

    @staticmethod
    def none():
        return KeyPoints(template_id="None", coords=[0, 0], states=["invisible"])


def is_keypoints(cls: type) -> bool:
    """Check if a class is a subclass of Keypoints.

    Parameters:
        cls (type): The class to check.

    Returns:
        bool: True if the class is a subclass of KeyPoints, False otherwise.
    """
    return issubclass(cls, KeyPoints)


def map_back2front_vertices(keypoints: KeyPoints) -> list:
    """Utility function to map back format for KeyPoint to front vertices format

    Args:
        keypoints (KeyPoints): Keypoints to map

    Raises:
        ValueError: if keypoints is ill-formed

    Returns:
        dict: keypoint list for vertices front format
    """
    # Check coords are even
    if len(keypoints.coords) % 2 != 0:
        raise ValueError("There must be an even number of coords")

    result = []
    if keypoints.states is not None:
        num_points = len(keypoints.coords) // 2
        if len(keypoints.states) != num_points:
            raise ValueError("There must be the same number of states than points")

        result = [
            {"x": x, "y": y, "features": {"state": state}}
            for (x, y), state in zip(
                zip(keypoints.coords[0::2], keypoints.coords[1::2]), keypoints.states
            )
        ]
    else:
        result = [
            {"x": x, "y": y}
            for x, y in zip(keypoints.coords[0::2], keypoints.coords[1::2])
        ]
    return result
