# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_schema import DatasetItem
from pixano.features.schemas.annotations.bbox import BBox
from pixano.features.schemas.annotations.keypoints import KeyPoints
from pixano.features.schemas.entities.entity import Entity
from pixano.features.schemas.views.image import Image
from pixano.features.schemas.views.video import Video


class MyEntity(Entity):
    category: str = "none"


@pytest.fixture
def dataset_item_image_bboxes_keypoint():
    class Schema(DatasetItem):
        image: Image
        metadata: str
        entities: list[Entity]
        bboxes: list[BBox]
        keypoint: KeyPoints

    return Schema


@pytest.fixture
def dataset_item_image_bboxes_keypoints():
    class Schema(DatasetItem):
        view: Image
        metadata: str
        entities: list[MyEntity]
        bbox: list[BBox]
        keypoint: list[KeyPoints]

    return Schema


@pytest.fixture
def dataset_item_video_bboxes_keypoint():
    class Schema(DatasetItem):
        view: Video
        metadata: str
        entities: list[MyEntity]
        bbox: list[BBox]
        keypoint: list[KeyPoints]

    return Schema


@pytest.fixture
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


@pytest.fixture
def dataset_item_image_embeddings(embedding_8):
    class Schema(DatasetItem):
        image: Image
        categories: tuple[str, ...]
        other_categories: list[int]
        entities: list[MyEntity]
        embeddings: list[embedding_8]

    return Schema
