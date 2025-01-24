# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import Conversation, Image, Message

from .image import ImageFolderBuilder


class DefaultVqaDatasetItem(DatasetItem):
    """Default VQA DatasetItem Schema."""

    image: Image
    conversations: list[Conversation]
    messages: list[Message]


class MultiviewVqaDatasetItem(DatasetItem):
    """Default Mulitiview DatasetItem Schema. (incomplete, will add views at init)."""

    conversations: list[Conversation]
    messages: list[Message]


class VqaFolderBuilder(ImageFolderBuilder):
    """Builder for vqa datasets stored in a folder."""

    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        info: DatasetInfo,
        dataset_item: type[DatasetItem] = DefaultVqaDatasetItem,
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
        dataset_item = self._getMultiViewDefaultSchema(
            Path(source_dir), dataset_item, DefaultVqaDatasetItem, MultiviewVqaDatasetItem
        )
        if not hasattr(info, "workspace") or info.workspace is None or info.workspace == WorkspaceType.UNDEFINED:
            info.workspace = WorkspaceType.IMAGE_VQA
        super().__init__(
            source_dir=source_dir, target_dir=target_dir, dataset_item=dataset_item, info=info, url_prefix=url_prefix
        )
