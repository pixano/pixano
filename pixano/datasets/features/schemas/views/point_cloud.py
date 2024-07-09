# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class PointCloud(View):
    """Point Cloud Lance Model."""

    url: str


def is_point_cloud(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of PointCloud."""
    return issubclass_strict(cls, PointCloud, strict)


def create_point_cloud(
    url: str, id: str = "", item_ref: ItemRef = ItemRef.none(), parent_ref: ViewRef = ViewRef.none()
) -> PointCloud:
    """Create a PointCloud instance.

    Args:
        url (str): The point cloud URL.
        id (str, optional): Point cloud ID.
        item_ref (ItemRef, optional): Item reference.
        parent_ref (ViewRef, optional): Parent view reference.

    Returns:
        _description_
    """
    return PointCloud(url=url, id=id, item_ref=item_ref, parent_ref=parent_ref)
