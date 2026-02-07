# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pixano.app.settings import Settings
from pixano.inference.provider import InferenceProvider


@patch("pixano.app.routers.inference.PixanoInferenceProvider.connect")
def test_connect_inference(
    mock_connect,
    empty_app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    empty_app, empty_settings, empty_client = empty_app_and_settings_with_client

    # Create a mock provider
    mock_provider = MagicMock(spec=InferenceProvider)
    mock_provider.name = "test-provider"
    mock_connect.return_value = mock_provider

    url = "/inference/connect?url=http://valid_url.com"

    response = empty_client.post(url)
    assert response.status_code == 200
    assert response.json() == {"status": "connected", "provider": "test-provider@valid_url.com:80"}
    assert "test-provider@valid_url.com:80" in empty_settings.inference_providers


def test_connect_inference_error(
    empty_app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    empty_app, empty_settings, empty_client = empty_app_and_settings_with_client

    url = "/inference/connect?url=wrongurl.wrongurl"

    response = empty_client.post(url)
    assert response.status_code == 404
    assert "wrongurl.wrongurl" in response.json()["detail"]
