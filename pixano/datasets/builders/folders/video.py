# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType
from pixano.datasets.workspaces.dataset_items import DefaultVideoDatasetItem

from .base import FolderBaseBuilder


# TODO: Add more video extensions supported by ffmpeg
VIDEO_EXTENSIONS = [
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",
    ".vob",
]


class VideoFolderBuilder(FolderBaseBuilder):
    """Builder for video datasets stored in a folder."""

    EXTENSIONS = VIDEO_EXTENSIONS
    WORKSPACE_TYPE = WorkspaceType.VIDEO
    DEFAULT_SCHEMA: type[DatasetItem] = DefaultVideoDatasetItem
