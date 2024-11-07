# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class PointCloud(View):
    """Point Cloud view.

    Attributes:
        url: The point cloud URL.
    """

    url: str


def is_point_cloud(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `PointCloud`."""
    return issubclass_strict(cls, PointCloud, strict)


def create_point_cloud(
    url: str, id: str = "", item_ref: ItemRef = ItemRef.none(), parent_ref: ViewRef = ViewRef.none()
) -> PointCloud:
    """Create a `PointCloud` instance.

    Args:
        url: The point cloud URL.
        id: Point cloud ID.
        item_ref: Item reference.
        parent_ref: Parent view reference.

    Returns:
        The created `PointCloud` instance.
    """
    return PointCloud(url=url, id=id, item_ref=item_ref, parent_ref=parent_ref)
