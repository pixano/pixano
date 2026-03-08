# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pixano.utils import issubclass_strict

from ..records import RecordComponent


class View(RecordComponent):
    """View base class.
    Views are used to define a view in a dataset such as an image, a point cloud, a text.

    Attributes:
        logical_name: Logical view name (sensor/modality identifier, e.g. "front_camera", "thermal", "lidar").
    """

    logical_name: str = ""


def is_view(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `View` or subclass of `View`."""
    return issubclass_strict(cls, View, strict)
