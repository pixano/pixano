# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.datasets import DatasetBrowser
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo


def test_get_browser(
    app_and_settings: tuple[FastAPI, Settings],
    info_dataset_image_bboxes_keypoint: DatasetInfo,
    info_dataset_multi_view_tracking_and_image: DatasetInfo,
    browser_dataset_image_bboxes_keypoint: DatasetBrowser,
    browser_dataset_multi_view_tracking_and_image: DatasetBrowser,
):
    app, settings = app_and_settings

    info_dataset_image_bboxes_keypoint.id = "dataset_image_bboxes_keypoint"
    info_dataset_multi_view_tracking_and_image.id = "dataset_multi_view_tracking_and_image"

    infos = [info_dataset_image_bboxes_keypoint, info_dataset_multi_view_tracking_and_image]
    outputs = [browser_dataset_image_bboxes_keypoint, browser_dataset_multi_view_tracking_and_image]

    client = TestClient(app)
    for info, output in zip(infos, outputs):
        response = client.get(f"/browser/{info.id}")
        assert response.status_code == 200
        browser = DatasetBrowser.model_validate(response.json())
        # generated dataset doesn't have consistent fields order, so we sort both before comparison
        browser.table_data.columns.sort(key=lambda x: x.name)
        output.table_data.columns.sort(key=lambda x: x.name)
        assert browser == output

    response = client.get("/browser/wrong_dataset")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {str(settings.data_dir)}."}
