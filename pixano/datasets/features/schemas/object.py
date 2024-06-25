# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.registry import _register_schema_internal

from ..types.bbox import BBox
from ..types.compressed_rle import CompressedRLE
from ..types.keypoints import KeyPoints
from .base_schema import BaseSchema


@_register_schema_internal
class Object(BaseSchema):
    """Object Lance Model."""

    item_id: str
    view_id: str
    bbox: BBox = BBox.none()
    mask: CompressedRLE = CompressedRLE.none()
    keypoints: KeyPoints = KeyPoints.none()


def is_object(cls: type) -> bool:
    """Check if a class is a subclass of Object.

    Args:
        cls (type): The class to check.

    Returns:
        bool: True if the class is a subclass of Object, False otherwise.
    """
    return issubclass(cls, Object)
