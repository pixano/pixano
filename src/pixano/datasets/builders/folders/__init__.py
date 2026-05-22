# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .folder_base_builder import FolderBaseBuilder
from .image import ImageFolderBuilder
from .mel import MelFolderBuilder
from .point_cloud import PointCloudFolderBuilder
from .video import VideoFolderBuilder
from .vqa import VQAFolderBuilder


__all__ = [
    "FolderBaseBuilder",
    "ImageFolderBuilder",
    "MelFolderBuilder",
    "PointCloudFolderBuilder",
    "VideoFolderBuilder",
    "VQAFolderBuilder",
]

# tri3d is an optional external dependency — only expose Dataset3DBuilder when it's installed.
try:
    from .builder_3d import Dataset3DBuilder

    __all__ = [*__all__, "Dataset3DBuilder"]
except ImportError:
    pass
