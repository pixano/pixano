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
    provider.segmentation = AsyncMock()
    provider.tracking = AsyncMock()
    provider.detection = AsyncMock()
    provider.vlm = AsyncMock()
    provider.list_models = AsyncMock(return_value=[])
    provider.get_capabilities = AsyncMock()
    provider.get_server_info = AsyncMock(
        return_value=ServerInfo(
            app_name="pixano-inference",
            app_version="0.6.0",
            app_description="Pixano Inference Server",
            num_cpus=8,
            num_gpus=1,
            num_nodes=1,
            gpus_used=0.0,
            gpu_to_model={"0": "sam2"},
            models=["sam2", "grounding-dino"],
            models_to_capability={"sam2": "segmentation", "grounding-dino": "detection"},
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
    provider.segmentation = AsyncMock()
    provider.tracking = AsyncMock()
    provider.detection = AsyncMock()
    provider.vlm = AsyncMock()
    provider.list_models = AsyncMock(return_value=[])
    provider.get_capabilities = AsyncMock()
    provider.get_server_info = AsyncMock(
        return_value=ServerInfo(
            app_name="pixano-inference",
            app_version="0.6.0",
            app_description="Pixano Inference Server",
            num_cpus=8,
            num_gpus=1,
            num_nodes=1,
            gpus_used=0.0,
            gpu_to_model={"0": "sam2"},
            models=["sam2", "grounding-dino"],
            models_to_capability={"sam2": "segmentation", "grounding-dino": "detection"},
        )
    )

    return provider


# Keep backwards compatibility alias
simple_pixano_inference_client = simple_inference_provider
simple_pixano_inference_client_fn_scope = simple_inference_provider_fn_scope
