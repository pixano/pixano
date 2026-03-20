# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_schema import DatasetItem
from pixano.features import Entity, Image, SequenceFrame
from pixano.schemas.annotations.bbox import BBox
from pixano.schemas.annotations.compressed_rle import CompressedRLE
from pixano.schemas.annotations.keypoints import KeyPoints
from pixano.schemas.annotations.message import Message
from pixano.schemas.annotations.tracklet import Tracklet


@pytest.fixture(scope="session")
def dataset_item_image_bboxes_keypoint():
    class Schema(DatasetItem):
        image: Image
        metadata: str
        entities: list[Entity]
        bboxes: list[BBox]
        keypoint: KeyPoints

    return Schema


@pytest.fixture(scope="session")
def dataset_item_vqa():
    class Schema(DatasetItem):
        image: Image
        messages: list[Message]

    return Schema


@pytest.fixture(scope="session")
def dataset_item_image_bboxes_keypoints(entity_category):
    class Schema(DatasetItem):
        view: Image
        metadata: str
        entities: list[entity_category]
        bbox: list[BBox]
        keypoint: list[KeyPoints]

    return Schema


@pytest.fixture(scope="session")
def dataset_item_video_bboxes_keypoint(entity_category):
    class Schema(DatasetItem):
        view: list[SequenceFrame]
        metadata: str
        entities: list[entity_category]
        bbox: list[BBox]
        keypoint: list[KeyPoints]

    return Schema


@pytest.fixture(scope="session")
def dataset_item_bboxes_metadata():
    class CustomDatasetItem(DatasetItem):
        categories: tuple[str, ...]
        other_categories: list[int]
        image: Image
        entity: Entity
        bbox: list[BBox]
        name: str
        index: int

    return CustomDatasetItem


@pytest.fixture(scope="session")
def dataset_item_image_embeddings(entity_category, embedding_8):
    class Schema(DatasetItem):
        image: Image
        categories: tuple[str, ...]
        other_categories: list[int]
        entities: list[entity_category]
        embeddings: list[embedding_8]

    return Schema


@pytest.fixture(scope="session")
def dataset_item_multi_view_tracking_and_image(
    sequence_frame_category, entity_category, bbox_difficult, view_embedding_8
):
    class Schema(DatasetItem):
        categories: tuple[str, ...]
        other_categories: list[int]
        video: list[sequence_frame_category]
        image: Image
        entity_image: entity_category
        entities_video: list[Entity]
        bbox_image: bbox_difficult
        mask_image: CompressedRLE
        keypoints_image: list[KeyPoints]
        bboxes_video: list[BBox]
        keypoints_video: list[KeyPoints]
        tracklets: list[Tracklet]
        image_embedding: view_embedding_8
        video_embeddings: list[view_embedding_8]

    return Schema
