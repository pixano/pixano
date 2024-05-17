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
class BBox3D(pydantic.BaseModel):
    """A 3D bounding Box

    Attributes:
        position (list[float]): List of 3d position coordinates (TODO: give format?)
        size (list[float]): List of 3d box size (TODO: give meaning of each elem)
        heading (list[float]): orientation (TODO: more explanations?)
    """
    position: list[float]
    size: list[float]
    heading: float  # TODO : use list[float] instead (need to adapt VDP dataset)
