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


def test_get_rows(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings
    client = TestClient(app)

    response = client.get("/annotations/dataset_image_bboxes_keypoint/bboxes/?limit=2")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "bbox_1_0",
            "table_info": {"name": "bboxes", "group": "annotations", "base_schema": "BBox"},
            "data": {
                "item_ref": {"name": "item", "id": "1"},
                "view_ref": {"name": "image", "id": "image_1"},
                "entity_ref": {"name": "entities", "id": "entity_1_0"},
                "coords": [0.0, 0.0, 100.0, 100.0],
                "format": "xywh",
                "is_normalized": False,
                "confidence": 0.9,
            },
        },
        {
            "id": "bbox_1_1",
            "table_info": {"name": "bboxes", "group": "annotations", "base_schema": "BBox"},
            "data": {
                "item_ref": {"name": "item", "id": "1"},
                "view_ref": {"name": "image", "id": "image_1"},
                "entity_ref": {"name": "entities", "id": "entity_1_1"},
                "coords": [0.0, 0.0, 100.0, 100.0],
                "format": "xywh",
                "is_normalized": False,
                "confidence": 0.9,
            },
        },
    ]

    response = client.get("/annotations/dataset_image_bboxes_keypoint/bboxes/?limit=2&ids=0")
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid query parameters."}

    response = client.get("/annotations/dataset_image_bboxes_keypoint/bboxes/?ids=nothing")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_image_bboxes_keypoint/bboxes."}


def test_get_row(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings
    client = TestClient(app)

    response = client.get("/annotations/dataset_image_bboxes_keypoint/bboxes/bbox_1_0")
    assert response.status_code == 200
    assert response.json() == {
        "id": "bbox_1_0",
        "table_info": {"name": "bboxes", "group": "annotations", "base_schema": "BBox"},
        "data": {
            "item_ref": {"name": "item", "id": "1"},
            "view_ref": {"name": "image", "id": "image_1"},
            "entity_ref": {"name": "entities", "id": "entity_1_0"},
            "coords": [0.0, 0.0, 100.0, 100.0],
            "format": "xywh",
            "is_normalized": False,
            "confidence": 0.9,
        },
    }

    response = client.get("/annotations/dataset_image_bboxes_keypoint/bboxes/nothing")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_image_bboxes_keypoint/bboxes."}
