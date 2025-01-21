# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType

from .image import ImageFolderBuilder


class VqaFolderBuilder(ImageFolderBuilder):
    """Builder for vqa datasets stored in a folder."""

    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        dataset_item: type[DatasetItem],
        info: DatasetInfo,
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
        if info.workspace is None:
            info.workspace = WorkspaceType.VQA
        super().__init__(
            source_dir=source_dir, target_dir=target_dir, dataset_item=dataset_item, info=info, url_prefix=url_prefix
        )
