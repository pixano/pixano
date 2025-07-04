# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import patch

import polars as pl
from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.datasets import DatasetBrowser
from pixano.app.settings import Settings
from pixano.datasets.dataset_info import DatasetInfo


def test_get_browser(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    info_dataset_image_bboxes_keypoint: DatasetInfo,
    info_dataset_multi_view_tracking_and_image: DatasetInfo,
    browser_dataset_image_bboxes_keypoint: DatasetBrowser,
    browser_dataset_multi_view_tracking_and_image: DatasetBrowser,
):
    app, settings, client = app_and_settings_with_client

    info_dataset_image_bboxes_keypoint.id = "dataset_image_bboxes_keypoint"
    info_dataset_multi_view_tracking_and_image.id = "dataset_multi_view_tracking_and_image"

    infos = [info_dataset_image_bboxes_keypoint, info_dataset_multi_view_tracking_and_image]
    outputs = [browser_dataset_image_bboxes_keypoint, browser_dataset_multi_view_tracking_and_image]

    for info, output in zip(infos, outputs):
        response = client.get(f"/browser/{info.id}?limit=50&skip=0")
        assert response.status_code == 200
        browser = DatasetBrowser.model_validate(response.json())
        # generated dataset doesn't have consistent fields order, so we sort both before comparison
        browser.table_data.columns.sort(key=lambda x: x.name)
        output.table_data.columns.sort(key=lambda x: x.name)
        assert browser.model_dump() == output.model_dump()

    response = client.get(f"/browser/{info_dataset_image_bboxes_keypoint.id}?limit=50&skip=0&where=split=%27test%27")
    assert response.status_code == 200
    browser = DatasetBrowser.model_validate(response.json())
    assert browser.item_ids == ["0", "2", "4"]

    response = client.get("/browser/wrong_dataset")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {str(settings.library_dir)}."}


def test_get_browser_semantic_search(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    info_dataset_multi_view_tracking_and_image: DatasetInfo,
    df_semantic_search: pl.DataFrame,
    browser_dataset_multi_view_tracking_and_image_semantic_search: DatasetBrowser,
):
    app, settings, client = app_and_settings_with_client

    info_dataset_multi_view_tracking_and_image.id = "dataset_multi_view_tracking_and_image"

    def _mock_to_polars(self):
        return df_semantic_search

    with patch("lancedb.query.LanceQueryBuilder.to_polars", _mock_to_polars):
        response = client.get(
            f"/browser/{info_dataset_multi_view_tracking_and_image.id}?limit=50&skip=0&query=metadata_0&embedding_table=image_embedding"
        )
    assert response.status_code == 200
    browser = DatasetBrowser.model_validate(response.json())
    # generated dataset doesn't have consistent fields order, so we sort both before comparison
    browser.table_data.columns.sort(key=lambda x: x.name)
    browser_dataset_multi_view_tracking_and_image_semantic_search.table_data.columns.sort(key=lambda x: x.name)
    assert browser == browser_dataset_multi_view_tracking_and_image_semantic_search

    response = client.get("/browser/wrong_dataset")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {str(settings.library_dir)}."}

    response = client.get("/browser/dataset_multi_view_tracking_and_image?limit=50&skip=0&query=metadata_0")
    assert response.status_code == 400
    assert response.json() == {"detail": "Both query and model_name should be provided for semantic search."}

    response = client.get("/browser/dataset_multi_view_tracking_and_image?limit=50&skip=0&embedding_table=wrong_table")
    assert response.status_code == 400
    assert response.json() == {"detail": "Both query and model_name should be provided for semantic search."}

    response = client.get(
        "/browser/dataset_multi_view_tracking_and_image?limit=50&skip=0&query=text&embedding_table=wrong_table"
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Table wrong_table not found in dataset dataset_multi_view_tracking_and_image."
    }

    response = client.get(
        "/browser/dataset_multi_view_tracking_and_image?limit=50&skip=0&query=text&embedding_table=image"
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Table image is not a view embedding table."}


def test_get_item_ids(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    info_dataset_image_bboxes_keypoint: DatasetInfo,
    browser_dataset_image_bboxes_keypoint: DatasetBrowser,
):
    app, settings, client = app_and_settings_with_client

    info_dataset_image_bboxes_keypoint.id = "dataset_image_bboxes_keypoint"

    response = client.get(f"/browser/item_ids/{info_dataset_image_bboxes_keypoint.id}")
    assert response.status_code == 200
    assert browser_dataset_image_bboxes_keypoint.item_ids == response.json()
