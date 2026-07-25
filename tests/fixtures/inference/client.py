# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import AsyncMock, MagicMock

import pytest

from pixano.inference.provider import InferenceProvider
from pixano.inference.types import InferenceTask, ServerInfo


def _make_mock_provider() -> InferenceProvider:
    provider = MagicMock(spec=InferenceProvider)
    provider.name = "mock-provider"
    provider.url = "http://localhost:8081"

    # Setup async task methods (new vocabulary)
    provider.image_mask_generation = AsyncMock()
    provider.video_mask_generation = AsyncMock()
    provider.submit_video_mask_generation_job = AsyncMock()
    provider.get_video_mask_generation_job = AsyncMock()
    provider.cancel_video_mask_generation_job = AsyncMock()
    provider.detection = AsyncMock()
    provider.vlm = AsyncMock()
    provider.embedding = AsyncMock()
    provider.close = AsyncMock()
    provider.list_models = AsyncMock(return_value=[])
    provider.get_server_info = AsyncMock(
        return_value=ServerInfo(
            version="0.6.0",
            models=["sam2", "grounding-dino"],
            models_to_task={
                "sam2": InferenceTask.MASK_GENERATION.value,
                "grounding-dino": InferenceTask.DETECTION.value,
            },
        )
    )
    return provider


@pytest.fixture(scope="session")
def simple_inference_provider() -> InferenceProvider:
    """Create a mock inference provider for testing."""
    return _make_mock_provider()


@pytest.fixture()
def simple_inference_provider_fn_scope() -> InferenceProvider:
    """Create a mock inference provider for testing (function scope)."""
    return _make_mock_provider()


# Keep backwards compatibility alias
simple_pixano_inference_client = simple_inference_provider
simple_pixano_inference_client_fn_scope = simple_inference_provider_fn_scope
