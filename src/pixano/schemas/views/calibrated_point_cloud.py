# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

from lancedb.pydantic import Vector

from pixano.schemas.views.point_cloud import PointCloud
from pixano.utils import issubclass_strict


class CalibratedPointCloud(PointCloud):
    """Calibrated point cloud view.

    Attributes:
        extrinsic_matrix: A 4x4 matrix representing the transformation from the LiDAR frame to the world frame.
                         (R | t)     where R is a 3x3 rotation matrix and t is a 3x1 translation vector.
                         (0 0 0 1)   the last row is [0, 0, 0, 1] for homogeneous coordinates.

        ego_to_world: A 4x4 matrix representing the transformation from the ego frame to the world frame.
                      in the same format as extrinsic_matrix.
    """

    # Extrinsics
    extrinsic_matrix: Vector(16)

    # Ego pose
    ego_to_world: Vector(16)


def is_calibrated_pointcloud(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of ``CalibratedPointcloud``."""
    return issubclass_strict(cls, CalibratedPointCloud, strict)
