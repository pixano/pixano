# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import tempfile
from pathlib import Path

import pytest
import shortuuid

from pixano.datasets.dataset import Dataset
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY


LIBRARY_DIR = ASSETS_DIRECTORY / "library"


@pytest.fixture(scope="session")
def dataset_image_bboxes_keypoint() -> Dataset:
    return Dataset.find("dataset_image_bboxes_keypoint", LIBRARY_DIR)


@pytest.fixture(scope="session")
def dataset_multi_view_tracking_and_image() -> Dataset:
    return Dataset.find("dataset_multi_view_tracking_and_image", LIBRARY_DIR)


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
    dataset = Dataset.find("dataset_image_bboxes_keypoint", LIBRARY_DIR)
    temp_folder = Path(tempfile.mkdtemp())
    dataset._copy_dataset(temp_folder)
    dataset.info.id = id
    dataset.info.to_json(dataset._info_file)
    return dataset


# TODO: extract dataset creation from test but seems easier to do it in the test because of the fixtures
# def test_create_library_dataset_builder_image_bboxes_keypoint(
#     dataset_builder_image_bboxes_keypoint,
#     dataset_builder_multi_view_tracking_and_image,
# ):
#     import lancedb

#     from tests.assets.sample_data.metadata import ASSETS_DIRECTORY

#     dataset_builder_image_bboxes_keypoint.info.id = "dataset_image_bboxes_keypoint"
#     dataset_builder_multi_view_tracking_and_image.info.id = "dataset_multi_view_tracking_and_image"
#     library_dir = ASSETS_DIRECTORY / "library"
#     dataset_builder_image_bboxes_keypoint_target_dir = library_dir / "dataset_image_bboxes_keypoint"
#     dataset_builder_image_bboxes_keypoint_target_dir.mkdir(exist_ok=True)
#     dataset_builder_image_bboxes_keypoint.target_dir = dataset_builder_image_bboxes_keypoint_target_dir
#     dataset_builder_image_bboxes_keypoint.db = lancedb.connect(
#         dataset_builder_image_bboxes_keypoint.target_dir / Dataset._DB_PATH
#     )

#     dataset_builder_multi_view_tracking_and_image_target_dir = library_dir / "dataset_multi_view_tracking_and_image"
#     dataset_builder_multi_view_tracking_and_image_target_dir.mkdir(exist_ok=True)
#     dataset_builder_multi_view_tracking_and_image.target_dir = (
#         dataset_builder_multi_view_tracking_and_image_target_dir
#     )
#     dataset_builder_multi_view_tracking_and_image.db = lancedb.connect(
#         dataset_builder_multi_view_tracking_and_image.target_dir / Dataset._DB_PATH
#     )

#     dataset_builder_image_bboxes_keypoint.build(mode="overwrite")
#     dataset_builder_multi_view_tracking_and_image.build(mode="overwrite")
