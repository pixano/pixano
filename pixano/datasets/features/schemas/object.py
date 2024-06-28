# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.registry import _register_schema_internal
from pixano.datasets.utils import is_obj_of_type

from ..types.bbox import BBox
from ..types.compressed_rle import CompressedRLE
from ..types.keypoints import KeyPoints
from .base_schema import BaseSchema


@_register_schema_internal
class Object(BaseSchema):
    """Object Lance Model."""

    item_id: str
    view_id: str


class ImageObject(Object):
    """Object for images."""

    bbox: BBox = BBox.none()
    mask: CompressedRLE = CompressedRLE.none()
    keypoints: KeyPoints = KeyPoints.none()


def is_object(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Object or subclass of Object."""
    return is_obj_of_type(cls, Object, strict)


def is_image_object(cls: type, strict: bool = False) -> bool:
    """Check if a class is an ImageObject or subclass of ImageObject."""
    return is_obj_of_type(cls, ImageObject, strict)

def create_image_object(
    item_id: str,
    view_id: str,
    id: str | None = None,
    bbox: BBox = BBox.none(),
    mask: CompressedRLE = CompressedRLE.none(),
    keypoints: KeyPoints = KeyPoints.none(),
):
    """Create an ImageObject instance.

    Args:
        item_id (str): The item id.
        view_id (str): The view id.
        id (str | None, optional): The object id. If None, a random id is generated.
        bbox (BBox, optional): The bounding box of the object.
        mask (CompressedRLE, optional): The mask of the object.
        keypoints (KeyPoints, optional): The keypoints of the object.

    Returns:
        ImageObject: The created ImageObject instance.
    """
    return ImageObject(
        item_id=item_id,
        view_id=view_id,
        id=id,
        bbox=bbox,
        mask=mask,
        keypoints=keypoints,
    )
