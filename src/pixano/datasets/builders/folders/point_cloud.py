# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, Image, KeyPoints, PointCloud, Record

from .folder_base_builder import FolderBaseBuilder
from .image import IMAGE_EXTENSIONS


# Binary point-cloud formats produced by nuScenes and common lidar sensors.
POINT_CLOUD_EXTENSIONS = [".pcd", ".pcd.bin", ".bin", ".ply"]


class PointCloudFolderBuilder(FolderBaseBuilder):
    """Builder for point-cloud datasets stored in a folder.

    Expects a ``metadata.jsonl`` file in each split directory mapping record
    IDs to per-view file paths (see :class:`FolderBaseBuilder` for the format).
    Views may mix point-cloud files (``.pcd.bin``, ``.pcd``, …) with camera
    images (``.jpg``, ``.png``, …).
    """

    EXTENSIONS = IMAGE_EXTENSIONS + POINT_CLOUD_EXTENSIONS
    DEFAULT_INFO = DatasetInfo(
        workspace=WorkspaceType.POINT_CLOUD,
        record=Record,
        entity=Entity,
        bbox=BBox,
        keypoint=KeyPoints,
        views={"point_cloud": PointCloud, "image": Image},
    )
