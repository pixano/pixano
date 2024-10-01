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
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY
from tests.fixtures.datasets.builders.builder import (
    DatasetBuilderImageBboxesKeypoint,
    DatasetBuilderMultiViewTrackingAndImage,
)


LIBRARY_DIR = ASSETS_DIRECTORY / "library"


@pytest.fixture(scope="session")
def dataset_image_bboxes_keypoint(dataset_item_image_bboxes_keypoint) -> Dataset:
    info_dataset_image_bboxes_keypoint = DatasetInfo(
        id="dataset_image_bboxes_keypoint",
        name="dataset_image_bboxes_keypoint",
        description="Description dataset_image_bboxes_keypoint.",
    )
    schemas = dataset_item_image_bboxes_keypoint
    dataset_builder_image_bboxes_keypoint = DatasetBuilderImageBboxesKeypoint(
        info=info_dataset_image_bboxes_keypoint,
        target_dir=LIBRARY_DIR / "dataset_image_bboxes_keypoint",
        schemas=schemas,
    )
    dataset_builder_image_bboxes_keypoint.db = lancedb.connect(
        dataset_builder_image_bboxes_keypoint.target_dir / Dataset._DB_PATH
    )
    return dataset_builder_image_bboxes_keypoint.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="session")
def dataset_multi_view_tracking_and_image(dataset_item_multi_view_tracking_and_image) -> Dataset:
    info = DatasetInfo(
        id="dataset_multi_view_tracking_and_image",
        name="dataset_multi_view_tracking_and_image",
        description="Description dataset_multi_view_tracking_and_image.",
    )
    schemas = dataset_item_multi_view_tracking_and_image

    dataset_builder_multi_view_tracking_and_image = DatasetBuilderMultiViewTrackingAndImage(
        info=info,
        target_dir=LIBRARY_DIR / "dataset_multi_view_tracking_and_image",
        schemas=schemas,
    )
    return dataset_builder_multi_view_tracking_and_image.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="function")
def dataset_image_bboxes_keypoint_copy() -> Dataset:
    id = shortuuid.uuid()
    dataset = Dataset.find("dataset_image_bboxes_keypoint", LIBRARY_DIR)
    temp_folder = Path(tempfile.mkdtemp())
    dataset._copy_dataset(temp_folder)
    dataset.info.id = id
    dataset.info.to_json(dataset._info_file)
    return dataset


@pytest.fixture(scope="function")
def dataset_multi_view_tracking_and_image_copy() -> Dataset:
    id = shortuuid.uuid()
    dataset = Dataset.find("dataset_multi_view_tracking_and_image", LIBRARY_DIR)
    temp_folder = Path(tempfile.mkdtemp())
    dataset._copy_dataset(temp_folder)
    dataset.info.id = id
    dataset.info.to_json(dataset._info_file)
    return dataset
