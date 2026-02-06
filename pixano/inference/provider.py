# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Abstract inference provider interface.

This module defines the abstract interface that all inference providers must implement.
Pixano uses this interface to communicate with different backends (pixano-inference,
OpenAI, Gemini, local models, etc.) in a uniform way.
"""

from abc import ABC, abstractmethod

from .exceptions import TaskNotSupportedError
from .types import (
    ImageMaskGenerationInput,
    ImageMaskGenerationResult,
    ImageZeroShotDetectionInput,
    ImageZeroShotDetectionResult,
    InferenceTask,
    ModelConfig,
    ModelInfo,
    ProviderCapabilities,
    ServerInfo,
    TextImageConditionalGenerationInput,
    TextImageConditionalGenerationResult,
    VideoMaskGenerationInput,
    VideoMaskGenerationResult,
)


class InferenceProvider(ABC):
    """Abstract interface for inference backends.

    This is the base class that all inference providers must implement.
    It defines a common interface for interacting with different inference
    backends, allowing Pixano to be agnostic to the specific backend used.

    Example:
        ```python
        from pixano.inference import get_provider

        # Get a provider instance
        provider = get_provider("pixano-inference", url="http://localhost:8000")

        # List available models
        models = await provider.list_models()

        # Generate masks
        result = await provider.generate_masks(input_data)
        ```
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'pixano-inference', 'openai', 'gemini')."""
        ...

    @abstractmethod
    async def get_capabilities(self) -> ProviderCapabilities:
        """Return what this provider can do.

        Returns:
            ProviderCapabilities describing supported tasks and features.
        """
        ...

    @abstractmethod
    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        """List available models, optionally filtered by task.

        Args:
            task: Optional task to filter models by.

        Returns:
            List of available models.
        """
        ...

    async def instantiate_model(self, provider: str, config: ModelConfig, timeout: int = 60) -> None:
        """Instantiate (load) a model.

        Args:
            provider: The model provider name (e.g., "sam2", "transformers").
            config: Configuration for the model.
            timeout: Timeout in seconds for model loading.

        Raises:
            TaskNotSupportedError: Model deployment is managed by the server administrator.
        """
        raise TaskNotSupportedError("Model deployment is managed by the server administrator")

    async def delete_model(self, model_name: str) -> None:
        """Delete (unload) a model.

        Args:
            model_name: Name of the model to delete.

        Raises:
            TaskNotSupportedError: Model deployment is managed by the server administrator.
        """
        raise TaskNotSupportedError("Model deployment is managed by the server administrator")

    @abstractmethod
    async def get_server_info(self) -> ServerInfo:
        """Get server information.

        Returns:
            ServerInfo with version, GPU info, models, readiness.
        """
        ...

    # --- Mask Generation ---

    @abstractmethod
    async def image_mask_generation(
        self,
        input_data: ImageMaskGenerationInput,
        timeout: float = 60.0,
    ) -> ImageMaskGenerationResult:
        """Generate masks for an image.

        Args:
            input_data: Input data for mask generation.
            timeout: Maximum time to wait for result.

        Returns:
            Mask generation result.
        """
        ...

    @abstractmethod
    async def video_mask_generation(
        self,
        input_data: VideoMaskGenerationInput,
        timeout: float = 120.0,
    ) -> VideoMaskGenerationResult:
        """Generate masks for video frames.

        Args:
            input_data: Input data for video mask generation.
            timeout: Maximum time to wait for result.

        Returns:
            Video mask generation result.
        """
        ...

    # --- Object Detection ---

    @abstractmethod
    async def image_zero_shot_detection(
        self,
        input_data: ImageZeroShotDetectionInput,
        timeout: float = 60.0,
    ) -> ImageZeroShotDetectionResult:
        """Detect objects in an image using zero-shot detection.

        Args:
            input_data: Input data for detection.
            timeout: Maximum time to wait for result.

        Returns:
            Detection result.
        """
        ...

    # --- Text Generation ---

    @abstractmethod
    async def text_image_conditional_generation(
        self,
        input_data: TextImageConditionalGenerationInput,
        timeout: float = 60.0,
    ) -> TextImageConditionalGenerationResult:
        """Generate text conditioned on images.

        Args:
            input_data: Input data for text generation.
            timeout: Maximum time to wait for result.

        Returns:
            Text generation result.
        """
        ...
