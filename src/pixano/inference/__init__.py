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
    InferenceRequestError,
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
    CAPABILITY_TO_TASK,
    TASK_TO_CAPABILITY,
    CompressedRLEData,
    DetectionInput,
    DetectionOutput,
    DetectionResult,
    EmbeddingInput,
    EmbeddingOutput,
    EmbeddingResult,
    ImageMaskGenerationInput,
    ImageMaskGenerationOutput,
    ImageMaskGenerationResult,
    InferenceTask,
    ModelInfo,
    NDArrayData,
    ServerInfo,
    UsageInfo,
    VideoMaskGenerationInput,
    VideoMaskGenerationJobStatus,
    VideoMaskGenerationOutput,
    VideoMaskGenerationResult,
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
    "InferenceRequestError",
    "InferenceTimeoutError",
    "InvalidRequestError",
    "ModelNotFoundError",
    "ProviderConnectionError",
    "ProviderNotFoundError",
    "TaskNotSupportedError",
    # Type definitions
    "InferenceTask",
    "CAPABILITY_TO_TASK",
    "TASK_TO_CAPABILITY",
    "ModelInfo",
    "ServerInfo",
    "CompressedRLEData",
    "NDArrayData",
    "ImageMaskGenerationInput",
    "ImageMaskGenerationOutput",
    "ImageMaskGenerationResult",
    "VideoMaskGenerationInput",
    "VideoMaskGenerationOutput",
    "VideoMaskGenerationResult",
    "VideoMaskGenerationJobStatus",
    "DetectionInput",
    "DetectionOutput",
    "DetectionResult",
    "EmbeddingInput",
    "EmbeddingOutput",
    "EmbeddingResult",
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
