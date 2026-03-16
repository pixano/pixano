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


def create_point_cloud(
    uri: str = "",
    id: str = "",
    record_id: str = "",
    logical_name: str = "",
    raw_bytes: bytes | None = None,
    preview: bytes = b"",
    preview_format: str = "",
) -> PointCloud:
    """Create a `PointCloud` instance.

    Args:
        uri: The point cloud URI. Can be empty when using embedded raw_bytes.
        id: Point cloud ID.
        record_id: Record ID.
        logical_name: Logical view name.
        raw_bytes: Raw point cloud bytes.
        preview: Thumbnail/preview bytes.
        preview_format: Preview format (e.g. "jpeg", "png").

    Returns:
        The created `PointCloud` instance.
    """
    return PointCloud(
        uri=uri,
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        raw_bytes=raw_bytes or b"",
        preview=preview,
        preview_format=preview_format,
    )
