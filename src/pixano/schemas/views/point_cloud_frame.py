# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pixano.utils import issubclass_strict
from .point_cloud import PointCloud


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
    record_id: str = "",
    logical_name: str = "",
    blob: bytes | None = None,
) -> PointCloudFrame:
    """Create a PointCloudFrame instance.

    Args:
        url: The point cloud URL. Can be empty when using embedded blob.
        timestamp: The timestamp of the frame.
        frame_index: The index of the frame in the sequence.
        id: PointCloudFrame ID.
        record_id: Record ID.
        logical_name: Logical view name.
        blob: Raw point cloud bytes.

    Returns:
        The created `PointCloudFrame` instance.
    """
    return PointCloudFrame(
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        url=url,
        blob=blob or b"",
        timestamp=timestamp,
        frame_index=frame_index,
    )
