# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi.testclient import TestClient

from tests.e2e.conftest import skip_no_server


pytestmark = [skip_no_server, pytest.mark.e2e]


# ---------------------------------------------------------------------------
# Model listing & server info
# ---------------------------------------------------------------------------


class TestRouterModels:
    def test_list_models(self, e2e_app_client: TestClient):
        response = e2e_app_client.get("/inference/models/list")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for model in data:
            assert "name" in model
            assert "task" in model

    def test_list_models_filtered(self, e2e_app_client: TestClient):
        response = e2e_app_client.get("/inference/models/list", params={"task": "image_mask_generation"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for model in data:
            assert model["task"] == "image_mask_generation"

    def test_server_info(self, e2e_app_client: TestClient):
        response = e2e_app_client.get("/inference/models/server-info")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert isinstance(data["models"], list)
        assert len(data["models"]) >= 1
        assert isinstance(data["models_to_task"], dict)
        assert len(data["models_to_task"]) >= 1


# ---------------------------------------------------------------------------
# Provider connection
# ---------------------------------------------------------------------------


class TestRouterConnect:
    def test_connected_providers(self, e2e_app_client: TestClient):
        response = e2e_app_client.get("/inference/connected")
        assert response.status_code == 200
        data = response.json()
        assert "pixano-inference" in data["providers"]

    def test_connect_real_server(self, e2e_app_client: TestClient, inference_url: str):
        response = e2e_app_client.post(
            "/inference/connect",
            params={"url": inference_url},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["provider"] == "pixano-inference"

    def test_connect_bad_url(self, e2e_app_client: TestClient):
        response = e2e_app_client.post(
            "/inference/connect",
            params={"url": "http://localhost:1"},
        )
        assert response.status_code == 404
