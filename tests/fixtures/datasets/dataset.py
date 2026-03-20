# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import shutil
import tempfile
from pathlib import Path

import pytest
import shortuuid

from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import BBox, Entity, Image, Message, Record
from pixano.schemas.annotations.compressed_rle import CompressedRLE
from pixano.schemas.annotations.keypoints import KeyPoints
from pixano.schemas.annotations.tracklet import Tracklet
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY
from tests.fixtures.datasets.builders.builder import (
    DatasetBuilderImageBboxesKeypoint,
    DatasetBuilderMultiViewTrackingAndImage,
    DatasetBuilderVQA,
)
from tests.fixtures.datasets.dataset_info import RecordWithCategories, RecordWithMetadata


LIBRARY_DIR = ASSETS_DIRECTORY / "library"


@pytest.fixture(scope="session")
def dataset_image_bboxes_keypoint() -> Dataset:
    info = DatasetInfo(
        id="dataset_image_bboxes_keypoint",
        name="dataset_image_bboxes_keypoint",
        description="Description dataset_image_bboxes_keypoint.",
        workspace=WorkspaceType.IMAGE,
        record=RecordWithMetadata,
        entity=Entity,
        bbox=BBox,
        views={"image": Image},
    )
    builder = DatasetBuilderImageBboxesKeypoint(
        info=info,
        target_dir=LIBRARY_DIR / "dataset_image_bboxes_keypoint",
    )
    return builder.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="session")
def dataset_vqa() -> Dataset:
    info = DatasetInfo(
        id="dataset_vqa",
        name="dataset_vqa",
        description="Description dataset_vqa.",
        workspace=WorkspaceType.IMAGE_VQA,
        record=Record,
        message=Message,
        views={"image": Image},
    )
    builder = DatasetBuilderVQA(
        info=info,
        target_dir=LIBRARY_DIR / "dataset_vqa",
    )
    return builder.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="session")
def dataset_multi_view_tracking_and_image(
    sequence_frame_category,
    entity_category,
    bbox_difficult,
    view_embedding_8,
) -> Dataset:
    info = DatasetInfo(
        id="dataset_multi_view_tracking_and_image",
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
    builder = DatasetBuilderMultiViewTrackingAndImage(
        info=info,
        target_dir=LIBRARY_DIR / "dataset_multi_view_tracking_and_image",
    )
    return builder.build(mode="overwrite", check_integrity="none")


def copy_dataset(dataset_id: str) -> Dataset:
    new_id = shortuuid.uuid()
    source = Dataset.find(dataset_id, LIBRARY_DIR)
    temp_folder = Path(tempfile.mkdtemp()) / dataset_id
    shutil.copytree(source.path, temp_folder)
    dataset = Dataset(temp_folder)
    dataset.info.id = new_id
    dataset.info.to_json(dataset._info_file)
    return dataset


@pytest.fixture(scope="function")
def dataset_image_bboxes_keypoint_copy(dataset_image_bboxes_keypoint: Dataset) -> Dataset:
    return copy_dataset("dataset_image_bboxes_keypoint")


@pytest.fixture(scope="function")
def dataset_multi_view_tracking_and_image_copy(dataset_multi_view_tracking_and_image: Dataset) -> Dataset:
    return copy_dataset("dataset_multi_view_tracking_and_image")


@pytest.fixture(scope="function")
def dataset_vqa_copy(dataset_vqa: Dataset) -> Dataset:
    return copy_dataset("dataset_vqa")
