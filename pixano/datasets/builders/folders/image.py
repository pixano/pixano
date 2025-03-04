# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType
from pixano.datasets.workspaces.dataset_items import DefaultImageDatasetItem

from .base import FolderBaseBuilder


# Image extensions supported by Pillow
IMAGE_EXTENSIONS = [
    ".blp",
    ".bmp",
    ".dib",
    ".bufr",
    ".cur",
    ".pcx",
    ".dcx",
    ".dds",
    ".ps",
    ".eps",
    ".fit",
    ".fits",
    ".fli",
    ".flc",
    ".ftc",
    ".ftu",
    ".gbr",
    ".gif",
    ".grib",
    ".h5",
    ".hdf",
    ".png",
    ".apng",
    ".jp2",
    ".j2k",
    ".jpc",
    ".jpf",
    ".jpx",
    ".j2c",
    ".icns",
    ".ico",
    ".im",
    ".iim",
    ".tif",
    ".tiff",
    ".jfif",
    ".jpe",
    ".jpg",
    ".jpeg",
    ".mpg",
    ".mpeg",
    ".msp",
    ".pcd",
    ".pxr",
    ".pbm",
    ".pgm",
    ".ppm",
    ".pnm",
    ".psd",
    ".bw",
    ".rgb",
    ".rgba",
    ".sgi",
    ".ras",
    ".tga",
    ".icb",
    ".vda",
    ".vst",
    ".webp",
    ".wmf",
    ".emf",
    ".xbm",
    ".xpm",
]


class ImageFolderBuilder(FolderBaseBuilder):
    """Builder for image datasets stored in a folder."""

    EXTENSIONS = IMAGE_EXTENSIONS
    WORKSPACE_TYPE = WorkspaceType.IMAGE
    DEFAULT_SCHEMA: type[DatasetItem] = DefaultImageDatasetItem
