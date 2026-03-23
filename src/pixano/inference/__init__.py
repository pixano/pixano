# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Pixano inference module.

This module provides the inference provider abstraction and concrete
implementations for different inference backends.

The provider pattern allows Pixano to communicate with different inference
backends (pixano-inference, OpenAI, Gemini, local models, etc.) in a uniform way.

Example:
    ```python
    from pixano.inference import get_provider, InferenceProvider

    # Get a provider instance
    provider = get_provider("pixano-inference", url="http://localhost:8000")

    # List available models
    models = await provider.list_models()
    ```
"""

# Core provider interface and registry
from .detection import detection
from .exceptions import (
    InferenceError,
    InferenceTimeoutError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderNotFoundError,
    TaskNotSupportedError,
)
from .provider import InferenceProvider

# Concrete providers (importing these registers them)
from .providers import (
    GeminiProvider,
    LMStudioProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    PixanoInferenceProvider,
    VLLMProvider,
)
from .registry import get_provider, is_provider_registered, list_providers, register_provider
from .segmentation import segmentation, tracking

# Type definitions
from .types import (
    CompressedRLEData,
    DetectionInput,
    DetectionOutput,
    DetectionResult,
    InferenceTask,
    ModelConfig,
    ModelInfo,
    NDArrayData,
    ProviderCapabilities,
    SegmentationInput,
    SegmentationOutput,
    SegmentationResult,
    ServerInfo,
    TrackingInput,
    TrackingOutput,
    TrackingResult,
    UsageInfo,
    VLMInput,
    VLMOutput,
    VLMResult,
)


__all__ = [
    # Provider interface and registry
    "InferenceProvider",
    "get_provider",
    "list_providers",
    "register_provider",
    "is_provider_registered",
    # Exceptions
    "InferenceError",
    "InferenceTimeoutError",
    "InvalidRequestError",
    "ModelNotFoundError",
    "ProviderConnectionError",
    "ProviderNotFoundError",
    "TaskNotSupportedError",
    # Type definitions
    "InferenceTask",
    "ModelConfig",
    "ModelInfo",
    "ProviderCapabilities",
    "ServerInfo",
    "CompressedRLEData",
    "NDArrayData",
    "SegmentationInput",
    "SegmentationOutput",
    "SegmentationResult",
    "TrackingInput",
    "TrackingOutput",
    "TrackingResult",
    "DetectionInput",
    "DetectionOutput",
    "DetectionResult",
    "VLMInput",
    "VLMOutput",
    "VLMResult",
    "UsageInfo",
    # Concrete providers
    "GeminiProvider",
    "LMStudioProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "PixanoInferenceProvider",
    "VLLMProvider",
    # Task functions
    "segmentation",
    "tracking",
    "detection",
]
