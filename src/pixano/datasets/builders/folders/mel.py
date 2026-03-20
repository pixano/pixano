# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Record, Text, TextSpan

from .folder_base_builder import FolderBaseBuilder
from .image import IMAGE_EXTENSIONS


class MelEntity(Entity):
    """Entity used by MEL image-text linking datasets."""

    name: str = ""


class MelFolderBuilder(FolderBaseBuilder):
    """Builder for MEL datasets stored in a folder."""

    EXTENSIONS = IMAGE_EXTENSIONS + [".txt"]
    DEFAULT_INFO = DatasetInfo(
        workspace=WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
        record=Record,
        entity=MelEntity,
        text_span=TextSpan,
        bbox=BBox,
        mask=CompressedRLE,
        views={"image": Image, "text": Text},
    )
