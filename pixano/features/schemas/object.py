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


from ..types import BBox, CompressedRLE
from .base_schema import BaseSchema
from .registry import _register_schema_internal


@_register_schema_internal()
class Object(BaseSchema):
    """Object Lance Model."""

    id: str
    item_id: str
    view_id: str


@_register_schema_internal()
class ObjectWithBBox(Object):
    """Object with Bounding Box Lance Model."""

    bbox: BBox


@_register_schema_internal()
class ObjectWithMask(Object):
    """Object with Mask Lance Model."""

    mask: CompressedRLE


@_register_schema_internal()
class ObjectWithBBoxAndMask(Object):
    """Object with Bounding Box and Mask Lance Model."""

    bbox: BBox
    mask: CompressedRLE
