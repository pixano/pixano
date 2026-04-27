# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from .view import View


class PointCloud(View):
    """Point Cloud view."""


def is_point_cloud(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `PointCloud`."""
    return issubclass_strict(cls, PointCloud, strict)
