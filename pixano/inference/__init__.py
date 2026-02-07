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
from .exceptions import (
    InferenceError,
    InferenceTimeoutError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderNotFoundError,
    TaskNotSupportedError,
)

# Legacy functions for backward compatibility during migration
from .mask_generation import image_mask_generation, video_mask_generation
from .provider import InferenceProvider

# Concrete providers (importing these registers them)
from .providers import PixanoInferenceProvider
from .registry import get_provider, is_provider_registered, list_providers, register_provider
from .text_image_conditional_generation import messages_to_prompt, text_image_conditional_generation

# Type definitions
from .types import (
    CompressedRLEData,
    ImageMaskGenerationInput,
    ImageMaskGenerationOutput,
    ImageMaskGenerationResult,
    ImageZeroShotDetectionInput,
    ImageZeroShotDetectionOutput,
    ImageZeroShotDetectionResult,
    InferenceTask,
    ModelConfig,
    ModelInfo,
    NDArrayData,
    ProviderCapabilities,
    ServerInfo,
    TextImageConditionalGenerationInput,
    TextImageConditionalGenerationOutput,
    TextImageConditionalGenerationResult,
    UsageInfo,
    VideoMaskGenerationInput,
    VideoMaskGenerationOutput,
    VideoMaskGenerationResult,
)
from .zero_shot_detection import image_zero_shot_detection


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
    "ImageMaskGenerationInput",
    "ImageMaskGenerationOutput",
    "ImageMaskGenerationResult",
    "VideoMaskGenerationInput",
    "VideoMaskGenerationOutput",
    "VideoMaskGenerationResult",
    "ImageZeroShotDetectionInput",
    "ImageZeroShotDetectionOutput",
    "ImageZeroShotDetectionResult",
    "TextImageConditionalGenerationInput",
    "TextImageConditionalGenerationOutput",
    "TextImageConditionalGenerationResult",
    "UsageInfo",
    # Concrete providers
    "PixanoInferenceProvider",
    # Legacy functions (for backward compatibility)
    "image_mask_generation",
    "video_mask_generation",
    "messages_to_prompt",
    "text_image_conditional_generation",
    "image_zero_shot_detection",
]
