# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel

from pixano.datasets.utils import is_obj_of_type

from .registry import _register_type_internal


@_register_type_internal
class BBox3D(BaseModel):
    """A 3D bounding Box.

    Attributes:
        position (list[float]): List of 3d position coordinates (TODO: give format?)
        size (list[float]): List of 3d box size (TODO: give meaning of each elem)
        heading (list[float]): orientation (TODO: more explanations?)
    """

    position: list[float]
    size: list[float]
    heading: float  # TODO : use list[float] instead (need to adapt VDP dataset)

    @staticmethod
    def none():
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            BBox3D: "None" BBox3D
        """
        return BBox3D(position=[0, 0, 0, 0, 0, 0], size=[0, 0, 0], heading=[0, 0, 0])


def is_bbox3d(cls: type, strict: bool = False) -> bool:
    """Check if a class is a BBox3D or subclass of BBox3D."""
    return is_obj_of_type(cls, BBox3D, strict)


def create_bbox3d(position: list[float], size: list[float], heading: float) -> BBox3D:
    """Create a BBox3D instance.

    Args:
        position (list[float]): The 3D position coordinates.
        size (list[float]): The 3D box size.
        heading (float): The orientation.

    Returns:
        BBox3D: The created BBox3D instance.
    """
    return BBox3D(position=position, size=size, heading=heading)
