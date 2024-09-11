# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.datasets import DatasetModel
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_features_values import DatasetFeaturesValues
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetSchema
from pixano.features.schemas.items.item import Item


def test_get_datasets_info(
    app_and_settings: tuple[FastAPI, Settings],
    info_dataset_image_bboxes_keypoint: DatasetInfo,
    info_dataset_multi_view_tracking_and_image: DatasetInfo,
):
    app, settings = app_and_settings

    infos = [info_dataset_image_bboxes_keypoint, info_dataset_multi_view_tracking_and_image]

    client = TestClient(app)
    response = client.get("/datasets/info")
    assert response.status_code == 200
    assert response.json() == [info.model_dump() for info in infos]


def test_get_datasets_info_not_found(empty_app_and_settings: tuple[FastAPI, Settings]):
    app, settings = empty_app_and_settings

    client = TestClient(app)
    response = client.get("/datasets/info")
    assert response.status_code == 404
    assert response.json() == {"detail": f"No datasets found in {str(settings.data_dir)}."}


def test_get_dataset_info(app_and_settings: tuple[FastAPI, Settings], info_dataset_image_bboxes_keypoint: DatasetInfo):
    app, settings = app_and_settings

    client = TestClient(app)
    response = client.get("/datasets/info/dataset_image_bboxes_keypoint")
    assert response.status_code == 200
    assert response.json() == info_dataset_image_bboxes_keypoint.model_dump()


def test_get_dataset(
    app_and_settings: tuple[FastAPI, Settings],
    dataset_schema_image_bboxes_keypoint: DatasetSchema,
    info_dataset_image_bboxes_keypoint: DatasetInfo,
):
    app, settings = app_and_settings

    client = TestClient(app)
    response = client.get("/datasets/dataset_image_bboxes_keypoint")
    assert response.status_code == 200
    dataset_model = DatasetModel.from_json(response.json())
    assert dataset_model.id == "dataset_image_bboxes_keypoint"
    assert dataset_model.dataset_schema.model_dump() == dataset_schema_image_bboxes_keypoint.model_dump()
    assert dataset_model.info == info_dataset_image_bboxes_keypoint
    assert dataset_model.feature_values == DatasetFeaturesValues()
    assert dataset_model.path == settings.data_dir / "dataset_image_bboxes_keypoint"
    assert dataset_model.previews_path == settings.data_dir / "dataset_image_bboxes_keypoint" / Dataset._PREVIEWS_PATH
    assert dataset_model.media_dir == settings.data_dir / "dataset_image_bboxes_keypoint" / "media"
    assert dataset_model.thumbnail == settings.data_dir / "dataset_image_bboxes_keypoint" / Dataset._THUMB_FILE

    response = client.get("/datasets/wrong_dataset")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {str(settings.data_dir)}."}
