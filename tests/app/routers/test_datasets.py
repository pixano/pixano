# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.datasets import DatasetModel
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_features_values import DatasetFeaturesValues
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetSchema


def test_get_datasets_info(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    info_model_dataset_image_bboxes_keypoint: DatasetInfo,
    info_model_dataset_multi_view_tracking_and_image: DatasetInfo,
    info_model_dataset_vqa: DatasetInfo,
):
    app, settings, client = app_and_settings_with_client

    info_model_dataset_image_bboxes_keypoint.id = "dataset_image_bboxes_keypoint"
    info_model_dataset_multi_view_tracking_and_image.id = "dataset_multi_view_tracking_and_image"
    info_model_dataset_vqa.id = "dataset_vqa"

    infos = [
        info_model_dataset_image_bboxes_keypoint,
        info_model_dataset_multi_view_tracking_and_image,
        info_model_dataset_vqa,
    ]

    response = client.get("/datasets/info")
    assert response.status_code == 200
    json_response = response.json()
    assert len(json_response) == len(infos)
    for info in infos:
        assert info.model_dump() in json_response


def test_get_datasets_info_not_found(empty_app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    app, settings, client = empty_app_and_settings_with_client

    response = client.get("/datasets/info")
    assert response.status_code == 404
    assert response.json() == {"detail": f"No datasets found in {str(settings.library_dir)}."}


def test_get_dataset_info(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    info_model_dataset_image_bboxes_keypoint: DatasetInfo,
):
    app, settings, client = app_and_settings_with_client

    info_model_dataset_image_bboxes_keypoint.id = "dataset_image_bboxes_keypoint"
    response = client.get("/datasets/info/dataset_image_bboxes_keypoint")
    assert response.status_code == 200
    assert response.json() == info_model_dataset_image_bboxes_keypoint.model_dump()


def test_get_dataset(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    dataset_schema_image_bboxes_keypoint: DatasetSchema,
    info_model_dataset_image_bboxes_keypoint: DatasetInfo,
):
    app, settings, client = app_and_settings_with_client

    info_model_dataset_image_bboxes_keypoint.id = "dataset_image_bboxes_keypoint"

    response = client.get("/datasets/dataset_image_bboxes_keypoint")
    assert response.status_code == 200
    dataset_model = DatasetModel.from_json(response.json())
    assert dataset_model.id == "dataset_image_bboxes_keypoint"
    assert dataset_model.dataset_schema.model_dump() == dataset_schema_image_bboxes_keypoint.model_dump()
    assert dataset_model.info == info_model_dataset_image_bboxes_keypoint
    assert dataset_model.feature_values == DatasetFeaturesValues()
    assert dataset_model.path == settings.library_dir / "dataset_image_bboxes_keypoint"
    assert (
        dataset_model.previews_path == settings.library_dir / "dataset_image_bboxes_keypoint" / Dataset._PREVIEWS_PATH
    )
    assert dataset_model.media_dir == settings.media_dir
    assert dataset_model.thumbnail == settings.library_dir / "dataset_image_bboxes_keypoint" / Dataset._THUMB_FILE

    response = client.get("/datasets/wrong_dataset")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {str(settings.library_dir)}."}


def test_get_table_count(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client

    response = client.get("/datasets/dataset_image_bboxes_keypoint/item/count")
    assert response.status_code == 200
    assert response.json() == 5

    response = client.get("/datasets/dataset_multi_view_tracking_and_image/video_embeddings/count")
    assert response.status_code == 200
    assert response.json() == 7

    response = client.get("/datasets/wrong_dataset/item/count")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {str(settings.library_dir)}."}

    response = client.get("/datasets/dataset_image_bboxes_keypoint/wrong_table/count")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table wrong_table not found in dataset"}
