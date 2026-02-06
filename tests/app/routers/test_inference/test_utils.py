# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.applications import FastAPI

from pixano.app.routers.inference.utils import get_provider_from_settings
from pixano.app.settings import Settings
from pixano.inference.provider import InferenceProvider


def test_get_provider_from_settings(
    app_and_settings: tuple[FastAPI, Settings], empty_app_and_settings: tuple[FastAPI, Settings]
):
    app, settings = app_and_settings

    # Create a mock provider and add it to settings
    mock_provider = MagicMock(spec=InferenceProvider)
    mock_provider.name = "test-provider"
    settings.inference_providers = {"test-provider": mock_provider}
    settings.default_inference_provider = "test-provider"

    provider = get_provider_from_settings(settings=settings)

    assert provider == mock_provider

    # Test with empty settings (no providers configured)
    empty_app, empty_settings = empty_app_and_settings
    empty_settings.inference_providers = {}
    empty_settings.default_inference_provider = None

    with pytest.raises(HTTPException) as exc_info:
        get_provider_from_settings(empty_settings)
    assert exc_info.value.status_code == 500
    assert "No inference provider connected" in exc_info.value.detail


def test_get_provider_from_settings_by_name():
    """Test getting a specific provider by name."""
    settings = MagicMock(spec=Settings)

    mock_provider1 = MagicMock(spec=InferenceProvider)
    mock_provider1.name = "provider1"
    mock_provider2 = MagicMock(spec=InferenceProvider)
    mock_provider2.name = "provider2"

    settings.inference_providers = {
        "provider1": mock_provider1,
        "provider2": mock_provider2,
    }
    settings.default_inference_provider = "provider1"

    # Get default provider
    provider = get_provider_from_settings(settings)
    assert provider == mock_provider1

    # Get specific provider by name
    provider = get_provider_from_settings(settings, provider_name="provider2")
    assert provider == mock_provider2

    # Get non-existent provider
    with pytest.raises(HTTPException) as exc_info:
        get_provider_from_settings(settings, provider_name="nonexistent")
    assert exc_info.value.status_code == 500
    assert "not found" in exc_info.value.detail
