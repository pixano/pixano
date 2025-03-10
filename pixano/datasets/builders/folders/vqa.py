# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import DefaultVQADatasetItem, WorkspaceType

from .image import ImageFolderBuilder


class VQAFolderBuilder(ImageFolderBuilder):
    """Builder for vqa datasets stored in a folder."""

    WORKSPACE_TYPE = WorkspaceType.IMAGE_VQA
    DEFAULT_SCHEMA: type[DatasetItem] = DefaultVQADatasetItem
