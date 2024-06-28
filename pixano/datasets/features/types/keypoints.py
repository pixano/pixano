# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel

from pixano.datasets.utils import is_obj_of_type

from .registry import _register_type_internal


@_register_type_internal
class KeyPoints(BaseModel):
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
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            KeyPoints: "None" KeyPoints
        """
        return KeyPoints(template_id="None", coords=[0, 0], states=["invisible"])


def map_back2front_vertices(keypoints: KeyPoints) -> list:
    """Utility function to map back format for KeyPoint to front vertices format.

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
            for (x, y), state in zip(zip(keypoints.coords[0::2], keypoints.coords[1::2]), keypoints.states)
        ]
    else:
        result = [{"x": x, "y": y} for x, y in zip(keypoints.coords[0::2], keypoints.coords[1::2])]
    return result


def is_keypoints(cls: type, strict: bool = False) -> bool:
    """Check if a class is a KeyPoints or subclass of KeyPoints."""
    return is_obj_of_type(cls, KeyPoints, strict)


def create_keypoints(template_id: str, coords: list[float], states: list[str]) -> KeyPoints:
    """Create a KeyPoints instance.

    Args:
        template_id (str): id of keypoint template
        coords (list[float]): List of 2D coordinates of the keypoints.
        states (list[str]): Status for each keypoint. ("visible", "invisible", "hidden")

    Returns:
        KeyPoints: The created KeyPoints instance.
    """
    return KeyPoints(template_id=template_id, coords=coords, states=states)
