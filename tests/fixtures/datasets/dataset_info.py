# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import BBox, Entity, Image, Message, Record
from pixano.schemas.annotations.compressed_rle import CompressedRLE
from pixano.schemas.annotations.keypoints import KeyPoints
from pixano.schemas.annotations.tracklet import Tracklet


class RecordWithMetadata(Record):
    """Record subclass used by the image_bboxes_keypoint builder tests."""

    metadata: str = ""


class RecordWithCategories(Record):
    """Record subclass used by the multi_view_tracking_and_image builder tests."""

    categories: tuple[str, ...] = ()
    other_categories: list[int] = []


@pytest.fixture()
def info_dataset_image_bboxes_keypoint():
    return DatasetInfo(
        name="dataset_image_bboxes_keypoint",
        description="Description dataset_image_bboxes_keypoint.",
        workspace=WorkspaceType.IMAGE,
        record=RecordWithMetadata,
        entity=Entity,
        bbox=BBox,
        views={"image": Image},
    )


@pytest.fixture()
def info_dataset_vqa():
    return DatasetInfo(
        name="dataset_vqa",
        description="Description dataset_vqa.",
        workspace=WorkspaceType.IMAGE_VQA,
        record=Record,
        message=Message,
        views={"image": Image},
    )


@pytest.fixture()
def info_dataset_multi_view_tracking_and_image(
    sequence_frame_category,
    entity_category,
    bbox_difficult,
    view_embedding_8,
):
    return DatasetInfo(
        name="dataset_multi_view_tracking_and_image",
        description="Description dataset_multi_view_tracking_and_image.",
        workspace=WorkspaceType.VIDEO,
        record=RecordWithCategories,
        entity=entity_category,
        bbox=bbox_difficult,
        mask=CompressedRLE,
        keypoint=KeyPoints,
        tracklet=Tracklet,
        views={
            "video": sequence_frame_category,
            "image": Image,
        },
    )
