# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, EntityDynamicState, KeyPoints, Record, SequenceFrame, Tracklet

from .folder_base_builder import FolderBaseBuilder
from .image import IMAGE_EXTENSIONS


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

    EXTENSIONS = VIDEO_EXTENSIONS + IMAGE_EXTENSIONS
    DEFAULT_INFO = DatasetInfo(
        workspace=WorkspaceType.VIDEO,
        record=Record,
        entity=Entity,
        entity_dynamic_state=EntityDynamicState,
        bbox=BBox,
        keypoint=KeyPoints,
        tracklet=Tracklet,
        views={"image": SequenceFrame},
    )
