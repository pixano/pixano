# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

from pixano.utils import issubclass_strict

from .point_cloud import PointCloud


class CalibratedPointcloud(PointCloud):
    """Calibrated point cloud view.

    Attributes:
        extrinsic_matrix: extrinsic_matrix. A 4x4 matrix representing the transformation from the LiDAR frame to the world frame.
                         (R | t)     where R is a 3x3 rotation matrix and t is a 3x1 translation vector.
                         (0 0 0 1)   the last row is [0, 0, 0, 1] for homogeneous coordinates.

        ego_to_world: ego_to_world. A 4x4 matrix representing the transformation from the ego frame to the world frame.
                      in the same format as extrinsic_matrix.
    """
    #Extrinsics
    extrinsic_matrix: list[list[float]]

    # Ego pose
    ego_to_world: list[list[float]]


def is_calibrated_pointcloud(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of ``CalibratedPointcloud``."""
    return issubclass_strict(cls, CalibratedPointcloud, strict)

def create_calibrated_pointcloud(
    uri: str = "",
    id: str = "",
    record_id: str = "",
    logical_name: str = "",
    raw_bytes: bytes | None = None,
    preview: bytes = b"",
    preview_format: str = "",
    extrinsic_matrix: list[list[float]] = None,
    ego_to_world: list[list[float]] = None
) -> CalibratedPointcloud:
    """Create a `CalibratedPointcloud` instance.

    Args:
        uri: The point cloud URI. Can be empty when using embedded raw_bytes.
        id: Point cloud ID.
        record_id: Record ID.
        logical_name: Logical view name.
        raw_bytes: Raw point cloud bytes.
        preview: Thumbnail/preview bytes.
        preview_format: Preview format (e.g. "jpeg", "png").
        extrinsic_matrix: Extrinsic matrix.
        ego_to_world: Ego-to-world transformation.

    Returns:
        The created `CalibratedPointcloud` instance.
    """
    return CalibratedPointcloud(
        uri=uri,
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        raw_bytes=raw_bytes or b"",
        preview=preview,
        preview_format=preview_format,
        extrinsic_matrix=extrinsic_matrix or [[0.0] * 4] * 4,
        ego_to_world=ego_to_world or [[0.0] * 4] * 4
    )
