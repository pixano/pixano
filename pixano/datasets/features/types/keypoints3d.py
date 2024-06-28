# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel

from pixano.datasets.utils import is_obj_of_type

from .registry import _register_type_internal


@_register_type_internal
class KeyPoints3D(BaseModel):
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
    visibles: list[bool]  # replace by features: list[dict] ?

    @staticmethod
    def none():
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            KeyPoints3D: "None" KeyPoints3D
        """
        return KeyPoints3D(template_id="None", coords=[0, 0, 0], visibles=[False])


def is_keypoints3d(cls: type) -> bool:
    """Check if a class is Keypoints3D or a subclass of Keypoints3D."""
    return is_obj_of_type(cls, KeyPoints3D)


def create_keypoints3d(template_id: str, coords: list[float], visibles: list[bool]) -> KeyPoints3D:
    """Create a KeyPoints3D instance.

    Args:
        template_id (str): The id of the keypoint template.
        coords (list[float]): The 3D coordinates of the keypoints.
        visibles (list[bool]): The visibility status for each keypoint.

    Returns:
        KeyPoints3D: The created KeyPoints3D instance.
    """
    return KeyPoints3D(template_id=template_id, coords=coords, visibles=visibles)
