# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import tempfile
from pathlib import Path

import lancedb
import pytest
import shortuuid

from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY
from tests.fixtures.datasets.builders.builder import (
    DatasetBuilderImageBboxesKeypoint,
    DatasetBuilderMultiViewTrackingAndImage,
    DatasetBuilderVQA,
)


LIBRARY_DIR = ASSETS_DIRECTORY / "library"


@pytest.fixture(scope="session")
def dataset_image_bboxes_keypoint(dataset_item_image_bboxes_keypoint) -> Dataset:
    info_dataset_image_bboxes_keypoint = DatasetInfo(
        id="dataset_image_bboxes_keypoint",
        name="dataset_image_bboxes_keypoint",
        description="Description dataset_image_bboxes_keypoint.",
        workspace=WorkspaceType.IMAGE,
    )
    dataset_builder_image_bboxes_keypoint = DatasetBuilderImageBboxesKeypoint(
        info=info_dataset_image_bboxes_keypoint,
        target_dir=LIBRARY_DIR / "dataset_image_bboxes_keypoint",
        dataset_item=dataset_item_image_bboxes_keypoint,
    )
    dataset_builder_image_bboxes_keypoint.db = lancedb.connect(
        dataset_builder_image_bboxes_keypoint.target_dir / Dataset._DB_PATH
    )
    return dataset_builder_image_bboxes_keypoint.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="session")
def dataset_vqa(dataset_item_vqa) -> Dataset:
    info_dataset_vqa = DatasetInfo(
        id="dataset_vqa",
        name="dataset_vqa",
        description="Description dataset_vqa.",
        workspace=WorkspaceType.IMAGE_VQA,
    )
    dataset_builder_vqa = DatasetBuilderVQA(
        info=info_dataset_vqa,
        target_dir=LIBRARY_DIR / "dataset_vqa",
        dataset_item=dataset_item_vqa,
    )
    dataset_builder_vqa.db = lancedb.connect(dataset_builder_vqa.target_dir / Dataset._DB_PATH)
    return dataset_builder_vqa.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="session")
def dataset_multi_view_tracking_and_image(dataset_item_multi_view_tracking_and_image) -> Dataset:
    info = DatasetInfo(
        id="dataset_multi_view_tracking_and_image",
        name="dataset_multi_view_tracking_and_image",
        description="Description dataset_multi_view_tracking_and_image.",
        workspace=WorkspaceType.VIDEO,
    )

    dataset_builder_multi_view_tracking_and_image = DatasetBuilderMultiViewTrackingAndImage(
        info=info,
        target_dir=LIBRARY_DIR / "dataset_multi_view_tracking_and_image",
        dataset_item=dataset_item_multi_view_tracking_and_image,
    )
    return dataset_builder_multi_view_tracking_and_image.build(mode="overwrite", check_integrity="none")


def copy_dataset(dataset_id: str) -> Dataset:
    id = shortuuid.uuid()
    dataset = Dataset.find(dataset_id, LIBRARY_DIR)
    temp_folder = Path(tempfile.mkdtemp())
    dataset._copy_dataset(temp_folder)
    dataset.info.id = id
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
