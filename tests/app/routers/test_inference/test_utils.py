# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi import HTTPException
from fastapi.applications import FastAPI
from pixano_inference.client import PixanoInferenceClient

from pixano.app.routers.inference.utils import get_client_from_settings
from pixano.app.settings import Settings


def test_get_client_from_settings(
    app_and_settings: tuple[FastAPI, Settings], empty_app_and_settings: tuple[FastAPI, Settings]
):
    app, settings = app_and_settings
    expected_client = settings.pixano_inference_client

    client = get_client_from_settings(settings=settings)

    assert client == expected_client and isinstance(client, PixanoInferenceClient)

    empty_app, empty_settings = empty_app_and_settings
    with pytest.raises(HTTPException) as exc_info:
        client = get_client_from_settings(empty_settings)
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Pixano Inference Client not configured"
