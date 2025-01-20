# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from enum import Enum
from typing import Literal, overload

from .image import ImageWorkspace
from .image_text_entity_linking import ImageTextEntityLinkingWorkspace
from .image_vqa_workspace import ImageVQAWorkspace
from .video import VideoWorkspace
from .workspace import Workspace


class WorkspaceType(Enum):
    """Workspace type.

    A workspace is a specific environment where the dataset is used. It defines what

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


@overload
def instatiate_workspace_by_type(
    workspace_type: Literal[WorkspaceType.IMAGE] = WorkspaceType.IMAGE,
) -> ImageWorkspace: ...
@overload
def instatiate_workspace_by_type(
    workspace_type: Literal[WorkspaceType.VIDEO] = WorkspaceType.VIDEO,
) -> VideoWorkspace: ...
@overload
def instatiate_workspace_by_type(
    workspace_type: Literal[WorkspaceType.IMAGE_VQA] = WorkspaceType.IMAGE_VQA,
) -> ImageVQAWorkspace: ...
@overload
def instatiate_workspace_by_type(
    workspace_type: Literal[WorkspaceType.IMAGE_TEXT_ENTITY_LINKING] = WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
) -> ImageTextEntityLinkingWorkspace: ...
@overload
def instatiate_workspace_by_type(
    workspace_type: Literal[WorkspaceType.UNDEFINED] = WorkspaceType.UNDEFINED,
) -> Workspace: ...
def instatiate_workspace_by_type(
    workspace_type: Literal[WorkspaceType.IMAGE]
    | Literal[WorkspaceType.VIDEO]
    | Literal[WorkspaceType.IMAGE_VQA]
    | Literal[WorkspaceType.IMAGE_TEXT_ENTITY_LINKING]
    | Literal[WorkspaceType.UNDEFINED] = WorkspaceType.UNDEFINED,
) -> ImageWorkspace | VideoWorkspace | ImageVQAWorkspace | ImageTextEntityLinkingWorkspace | Workspace:
    """Instatiate workspace by type."""
    match workspace_type:
        case WorkspaceType.IMAGE:
            return ImageWorkspace()
        case WorkspaceType.VIDEO:
            return VideoWorkspace()
        case WorkspaceType.IMAGE_VQA:
            return ImageVQAWorkspace()
        case WorkspaceType.IMAGE_TEXT_ENTITY_LINKING:
            return ImageTextEntityLinkingWorkspace()
        case _:
            raise ValueError("Workspace type not found")


__all__ = [
    "ImageWorkspace",
    "ImageTextEntityLinkingWorkspace",
    "ImageVQAWorkspace",
    "VideoWorkspace",
    "Workspace",
    "WorkspaceType",
    "instatiate_workspace_by_type",
]
