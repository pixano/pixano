# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .view import View
from .registry import _register_schema_internal


@_register_schema_internal
class PointCloud(View):
    """Point Cloud Lance Model."""

    url: str


def is_point_cloud(cls: type) -> bool:
    """Check if the given class is a subclass of PointCloud."""
    return issubclass(cls, PointCloud)
