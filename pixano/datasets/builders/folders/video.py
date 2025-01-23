# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import BBox, KeyPoints, SequenceFrame, Track, Tracklet

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


class DefaultVideoDatasetItem(DatasetItem):
    """Default Video DatasetItem Schema."""

    image: list[SequenceFrame]
    tracks: list[Track]
    tracklets: list[Tracklet]
    bboxes: list[BBox]
    keypoints: list[KeyPoints]


class VideoFolderBuilder(FolderBaseBuilder):
    """Builder for video datasets stored in a folder."""

    EXTENSIONS = VIDEO_EXTENSIONS

    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        info: DatasetInfo,
        dataset_item: type[DatasetItem] = DefaultVideoDatasetItem,
        url_prefix: Path | str | None = None,
    ) -> None:
        """Initialize the `VqaFolderBuilder`.

        Args:
            source_dir: The source directory for the dataset.
            target_dir: The target directory for the dataset.
            dataset_item: The dataset item schema.
            info: User informations (name, description, ...) for the dataset.
            url_prefix: The path to build relative URLs for the views. Useful to build dataset libraries to pass the
                relative path from the media directory.
        """
        if not hasattr(info, "workspace") or info.workspace is None or info.workspace == WorkspaceType.UNDEFINED:
            info.workspace = WorkspaceType.VIDEO
        super().__init__(
            source_dir=source_dir, target_dir=target_dir, dataset_item=dataset_item, info=info, url_prefix=url_prefix
        )
