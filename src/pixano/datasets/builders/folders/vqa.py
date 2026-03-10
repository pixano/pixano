# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import Entity, Image, Message, Record

from .image import ImageFolderBuilder


class VQAFolderBuilder(ImageFolderBuilder):
    """Builder for vqa datasets stored in a folder."""

    WORKSPACE_TYPE = WorkspaceType.IMAGE_VQA
    DEFAULT_INFO = DatasetInfo(
        workspace=WorkspaceType.IMAGE_VQA,
        record=Record,
        entity=Entity,
        message=Message,
        views={"image": Image},
    )
