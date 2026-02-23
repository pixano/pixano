# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class PointCloud(View):
    """Point Cloud view.

    Attributes:
        url: The point cloud URL. Empty when embedded.
        blob: Raw point cloud bytes. Empty when using filesystem URL.
    """

    url: str = ""
    blob: bytes = b""


def is_point_cloud(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `PointCloud`."""
    return issubclass_strict(cls, PointCloud, strict)


def create_point_cloud(
    url: str = "",
    id: str = "",
    item_id: str = "",
    parent_id: str = "",
    view_name: str = "",
    blob: bytes | None = None,
) -> PointCloud:
    """Create a `PointCloud` instance.

    Args:
        url: The point cloud URL. Can be empty when using embedded blob.
        id: Point cloud ID.
        item_id: Item ID.
        parent_id: Parent view ID.
        view_name: Logical view name.
        blob: Raw point cloud bytes.

    Returns:
        The created `PointCloud` instance.
    """
    return PointCloud(
        url=url,
        id=id,
        item_id=item_id,
        parent_id=parent_id,
        view_name=view_name,
        blob=blob or b"",
    )
