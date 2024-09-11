# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.settings import Settings


@pytest.mark.skip(reason="Already done in test_datasets.py")
def test_get_dataset(app_and_settings: tuple[FastAPI, Settings]):
    pass


def test_assert_table_in_group(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings
    client = TestClient(app)

    response = client.get("/annotations/dataset_image_bboxes_keypoint/bboxes/?limit=1")
    assert response.status_code == 200

    response = client.get("/annotations/dataset_image_bboxes_keypoint/keypoints/?limit=1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table keypoints is not in the annotations group table."}
