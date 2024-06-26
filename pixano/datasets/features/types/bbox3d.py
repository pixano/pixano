# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pydantic

from .registry import _register_type_internal


@_register_type_internal
class BBox3D(pydantic.BaseModel):
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
        """
        Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            BBox3D: "None" BBox3D
        """
        return BBox3D(position=[0, 0, 0, 0, 0, 0], size=[0, 0, 0], heading=[0, 0, 0])
