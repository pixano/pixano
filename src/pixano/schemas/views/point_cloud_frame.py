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
    uri: str = "",
    timestamp: float = 0.0,
    frame_index: int = 0,
    id: str = "",
    record_id: str = "",
    logical_name: str = "",
    raw_bytes: bytes | None = None,
    preview: bytes = b"",
    preview_format: str = "",
) -> PointCloudFrame:
    """Create a PointCloudFrame instance.

    Args:
        uri: The point cloud URI. Can be empty when using embedded raw_bytes.
        timestamp: The timestamp of the frame.
        frame_index: The index of the frame in the sequence.
        id: PointCloudFrame ID.
        record_id: Record ID.
        logical_name: Logical view name.
        raw_bytes: Raw point cloud bytes.
        preview: Thumbnail/preview bytes.
        preview_format: Preview format (e.g. "jpeg", "png").

    Returns:
        The created `PointCloudFrame` instance.
    """
    return PointCloudFrame(
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        uri=uri,
        raw_bytes=raw_bytes or b"",
        timestamp=timestamp,
        frame_index=frame_index,
        preview=preview,
        preview_format=preview_format,
    )
