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
import typing

from pixano.datasets.features.schemas.registry import _register_schema_internal

from ..types.bbox import BBox
from ..types.compressed_rle import CompressedRLE
from .base_schema import BaseSchema


class Object(BaseSchema):
    """Object Lance Model."""

    item_id: str
    view_id: str


class ObjectWithBBox(Object):
    """Object with Bounding Box Lance Model."""

    bbox: BBox


class ObjectWithMask(Object):
    """Object with Mask Lance Model."""

    mask: CompressedRLE


class ObjectWithBBoxAndMask(Object):
    """Object with Bounding Box and Mask Lance Model."""

    bbox: BBox
    mask: CompressedRLE


def is_object(cls: typing.Any) -> bool:
    """Check if a class is a subclass of Object.

    Args:
        cls (typing.Any): The class to check.

    Returns:
        bool: True if the class is a subclass of Object, False otherwise.
    """
    return issubclass(cls, Object)


_register_schema_internal(Object)
_register_schema_internal(ObjectWithBBox)
_register_schema_internal(ObjectWithMask)
_register_schema_internal(ObjectWithBBoxAndMask)