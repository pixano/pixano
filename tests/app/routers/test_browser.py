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
    json_browser_dataset_image_bboxes_keypoint: DatasetBrowser,
    json_browser_dataset_multi_view_tracking_and_image: DatasetBrowser,
):
    app, settings = app_and_settings

    infos = [info_dataset_image_bboxes_keypoint, info_dataset_multi_view_tracking_and_image]
    outputs = [json_browser_dataset_image_bboxes_keypoint, json_browser_dataset_multi_view_tracking_and_image]

    client = TestClient(app)
    for info, output in zip(infos, outputs):
        response = client.get(f"/browser/{info.id}")
        assert response.status_code == 200
        assert response.json() == output
