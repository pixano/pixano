# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Literal

from pydantic import model_validator

from pixano.datasets.utils import issubclass_strict

from .base_type import BaseType
from .registry import _register_type_internal


@_register_type_internal
class KeyPoints3D(BaseType):
    """A set of 3D keypoints.

    Attributes:
        template_id (str): id of keypoint template
        coords (list[float]): List of 3D coordinates of the keypoints.
        states: Literal["visible", "invisible", "hidden"]  # replace by features: list[dict] ?

    """

    template_id: str
    coords: list[float]
    states: list[Literal["visible", "invisble", "hidden"]]  # replace by features: list[dict] ?

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(self.coords) % 3 != 0:
            raise ValueError("There must be a multiple of 3 coords")
        elif any(coord < 0 for coord in self.coords):
            raise ValueError("Coordinates must be positive")
        if len(self.states) != len(self.coords) // 3:
            raise ValueError("There must be the same number of states than points")
        return self

    @staticmethod
    def none():
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            KeyPoints3D: "None" KeyPoints3D
        """
        return KeyPoints3D(template_id="N/A", coords=[0, 0, 0], states=["visible"])


def is_keypoints3d(cls: type, strict: bool = False) -> bool:
    """Check if a class is Keypoints3D or a subclass of Keypoints3D."""
    return issubclass_strict(cls, KeyPoints3D, strict)


def create_keypoints3d(
    template_id: str, coords: list[float], states: list[Literal["visible", "invisble", "hidden"]]
) -> KeyPoints3D:
    """Create a KeyPoints3D instance.

    Args:
        template_id (str): The id of the keypoint template.
        coords (list[float]): The 3D coordinates of the keypoints.
        states (list[Literal["visible", "invisble", "hidden"]]): The visibility status for each keypoint.

    Returns:
        KeyPoints3D: The created KeyPoints3D instance.
    """
    return KeyPoints3D(template_id=template_id, coords=coords, states=states)
