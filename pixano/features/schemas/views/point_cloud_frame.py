# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ..registry import _register_schema_internal
from .point_cloud import PointCloud


@_register_schema_internal
class PointCloudFrame(PointCloud):
    """Temporal point-cloud frame."""

    timestamp: float = 0.0
    frame_index: int = 0


def is_point_cloud_frame(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of PointCloudFrame."""
    return issubclass_strict(cls, PointCloudFrame, strict)


def create_point_cloud_frame(
    url: str = "",
    timestamp: float = 0.0,
    frame_index: int = 0,
    id: str = "",
    item_id: str = "",
    parent_id: str = "",
    view_name: str = "",
    blob: bytes | None = None,
) -> PointCloudFrame:
    """Create a PointCloudFrame instance."""
    return PointCloudFrame(
        id=id,
        item_id=item_id,
        parent_id=parent_id,
        view_name=view_name,
        url=url,
        blob=blob or b"",
        timestamp=timestamp,
        frame_index=frame_index,
    )

