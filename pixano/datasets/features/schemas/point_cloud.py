# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import shortuuid

from pixano.datasets.utils import issubclass_strict

from .registry import _register_schema_internal
from .view import View


@_register_schema_internal
class PointCloud(View):
    """Point Cloud Lance Model."""

    item_id: str
    url: str


def is_point_cloud(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of PointCloud."""
    return issubclass_strict(cls, PointCloud, strict)


def create_point_cloud(item_id: str, url: str, id: str | None = None) -> PointCloud:
    """Create a PointCloud instance.

    Args:
        item_id (str): The item id.
        url (str): The point cloud URL.
        id (str | None,  optional): The point cloud id. If None, a random id is generated.

    Returns:
        _description_
    """
    return PointCloud(item_id=item_id, url=url, id=id if id is not None else shortuuid.uuid())
