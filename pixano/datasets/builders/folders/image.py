# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import BBox, CompressedRLE, Entity, Image, KeyPoints

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


class DefaultImageDatasetItem(DatasetItem):
    """Default Image DatasetItem Schema."""

    image: Image
    objects: list[Entity]
    bbox: list[BBox]
    mask: list[CompressedRLE]
    keypoints: list[KeyPoints]


class ImageFolderBuilder(FolderBaseBuilder):
    """Builder for image datasets stored in a folder."""

    EXTENSIONS = IMAGE_EXTENSIONS

    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        info: DatasetInfo,
        dataset_item: type[DatasetItem] = DefaultImageDatasetItem,
        url_prefix: Path | str | None = None,
    ) -> None:
        """Initialize the `ImageFolderBuilder`.

        Args:
            source_dir: The source directory for the dataset.
            target_dir: The target directory for the dataset.
            dataset_item: The dataset item schema.
            info: User informations (name, description, ...) for the dataset.
            url_prefix: The path to build relative URLs for the views. Useful to build dataset libraries to pass the
                relative path from the media directory.
        """
        if info.workspace is None or info.workspace == WorkspaceType.UNDEFINED:
            info.workspace = WorkspaceType.IMAGE
        super().__init__(
            source_dir=source_dir, target_dir=target_dir, dataset_item=dataset_item, info=info, url_prefix=url_prefix
        )
