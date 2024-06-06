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

from pixano.datasets.features.schemas.registry import _register_schema_internal

from ..types.bbox import BBox
from ..types.compressed_rle import CompressedRLE
from .base_schema import BaseSchema


@_register_schema_internal
class Object(BaseSchema):
    """Object Lance Model."""

    item_id: str
    view_id: str
    bbox: BBox = BBox.none()
    mask: CompressedRLE = CompressedRLE.none()


def is_object(cls: type) -> bool:
    """Check if a class is a subclass of Object.

    Args:
        cls (type): The class to check.

    Returns:
        bool: True if the class is a subclass of Object, False otherwise.
    """
    return issubclass(cls, Object)
