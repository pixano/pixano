# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import AsyncMock, MagicMock

import pytest

from pixano.inference.provider import InferenceProvider
from pixano.inference.types import ServerInfo


@pytest.fixture(scope="session")
def simple_inference_provider() -> InferenceProvider:
    """Create a mock inference provider for testing."""
    provider = MagicMock(spec=InferenceProvider)
    provider.name = "mock-provider"
    provider.url = "http://localhost:8081"

    # Setup async methods
    provider.image_mask_generation = AsyncMock()
    provider.video_mask_generation = AsyncMock()
    provider.image_zero_shot_detection = AsyncMock()
    provider.text_image_conditional_generation = AsyncMock()
    provider.list_models = AsyncMock(return_value=[])
    provider.get_capabilities = AsyncMock()
    provider.get_server_info = AsyncMock(
        return_value=ServerInfo(
            version="0.1.0",
            models_loaded=2,
            num_gpus=1,
            gpu_info={"gpu_0": "NVIDIA A100"},
            models=["sam2", "grounding-dino"],
            models_to_task={"sam2": "image_mask_generation", "grounding-dino": "image_zero_shot_detection"},
            ready=True,
        )
    )

    return provider


@pytest.fixture()
def simple_inference_provider_fn_scope() -> InferenceProvider:
    """Create a mock inference provider for testing (function scope)."""
    provider = MagicMock(spec=InferenceProvider)
    provider.name = "mock-provider"
    provider.url = "http://localhost:8081"

    # Setup async methods
    provider.image_mask_generation = AsyncMock()
    provider.video_mask_generation = AsyncMock()
    provider.image_zero_shot_detection = AsyncMock()
    provider.text_image_conditional_generation = AsyncMock()
    provider.list_models = AsyncMock(return_value=[])
    provider.get_capabilities = AsyncMock()
    provider.get_server_info = AsyncMock(
        return_value=ServerInfo(
            version="0.1.0",
            models_loaded=2,
            num_gpus=1,
            gpu_info={"gpu_0": "NVIDIA A100"},
            models=["sam2", "grounding-dino"],
            models_to_task={"sam2": "image_mask_generation", "grounding-dino": "image_zero_shot_detection"},
            ready=True,
        )
    )

    return provider


# Keep backwards compatibility alias
simple_pixano_inference_client = simple_inference_provider
simple_pixano_inference_client_fn_scope = simple_inference_provider_fn_scope
