# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from enum import Enum

from .dataset_items import default_image_tables, default_video_tables, default_vqa_tables


class WorkspaceType(Enum):
    """Workspace type.

    A workspace is a specific environment where the dataset is used.

    Attributes:
        IMAGE: Image workspace.
        VIDEO: Video workspace.
        IMAGE_VQA: Image VQA workspace.
        IMAGE_TEXT_ENTITY_LINKING: Image text entity linking workspace.
        UNDEFINED: Undefined workspace.
    """

    IMAGE = "image"
    VIDEO = "video"
    IMAGE_VQA = "image_vqa"
    IMAGE_TEXT_ENTITY_LINKING = "image_text_entity_linking"
    UNDEFINED = "undefined"


__all__ = [
    "WorkspaceType",
    "default_image_tables",
    "default_video_tables",
    "default_vqa_tables",
]
