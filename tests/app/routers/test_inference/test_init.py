# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pixano_inference.client import PixanoInferenceClient

from pixano.app.settings import Settings


@patch("pixano.app.routers.inference.PixanoInferenceClient.connect")
def test_connect_inference(
    mock_connect,
    empty_app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    empty_app, empty_settings, empty_client = empty_app_and_settings_with_client

    expected_client = PixanoInferenceClient(url="http://valid_url.com", app_name="test")
    mock_connect.return_value = expected_client

    url = "/inference/connect/?url=valid_url.com"

    response = empty_client.post(url)
    assert response.status_code == 200
    assert response.json() is None
    assert empty_settings.pixano_inference_client == expected_client


def test_connect_inference_error(
    empty_app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    empty_app, empty_settings, empty_client = empty_app_and_settings_with_client

    url = "/inference/connect/?url=wrongurl.wrongurl"

    response = empty_client.post(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Impossible to connect to Pixano Inference from url: wrongurl.wrongurl"}
