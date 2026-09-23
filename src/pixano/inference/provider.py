# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Abstract inference provider interface.

This module defines the abstract interface that all inference providers must implement.
Pixano uses this interface to communicate with different backends (pixano-inference,
OpenAI, Gemini, local models, etc.) in a uniform way. Only discovery methods are abstract;
each task method defaults to raising `TaskNotSupportedError`, so a provider implements only
what its backend supports.
"""

from abc import ABC, abstractmethod

from .exceptions import TaskNotSupportedError
from .types import (
    DetectionInput,
    DetectionResult,
    EmbeddingInput,
    EmbeddingResult,
    ImageMaskGenerationInput,
    ImageMaskGenerationResult,
    InferenceTask,
    ModelInfo,
    ServerInfo,
    VideoMaskGenerationInput,
    VideoMaskGenerationJobStatus,
    VideoMaskGenerationResult,
    VLMInput,
    VLMResult,
)


class InferenceProvider(ABC):
    """Abstract interface for inference backends.

    Example:
        ```python
        from pixano.inference import get_provider

        provider = get_provider("pixano-inference", url="http://localhost:8000")
        models = await provider.list_models()
        result = await provider.image_mask_generation(input_data)
        ```
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'pixano-inference', 'openai', 'gemini')."""
        ...

    @abstractmethod
    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        """List available models, optionally filtered by task."""
        ...

    @abstractmethod
    async def get_server_info(self) -> ServerInfo:
        """Get server information (version, models, models_to_task)."""
        ...

    async def close(self) -> None:
        """Release any resources held by the provider (e.g. HTTP connections)."""
        return None

    # --- Image mask generation ---

    async def image_mask_generation(
        self,
        input_data: ImageMaskGenerationInput,
        timeout: float = 60.0,
    ) -> ImageMaskGenerationResult:
        """Generate masks for an image."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support image mask generation")

    # --- Video mask generation ---

    async def video_mask_generation(
        self,
        input_data: VideoMaskGenerationInput,
        timeout: float = 120.0,
    ) -> VideoMaskGenerationResult:
        """Generate masks for video frames (synchronous)."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support video mask generation")

    async def submit_video_mask_generation_job(
        self,
        input_data: VideoMaskGenerationInput,
        timeout: float = 30.0,
    ) -> VideoMaskGenerationJobStatus:
        """Submit an asynchronous video mask generation job."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support video mask generation")

    async def get_video_mask_generation_job(
        self,
        job_id: str,
        timeout: float = 30.0,
    ) -> VideoMaskGenerationJobStatus:
        """Fetch the current status of an asynchronous video mask generation job."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support video mask generation")

    async def cancel_video_mask_generation_job(
        self,
        job_id: str,
        timeout: float = 30.0,
    ) -> VideoMaskGenerationJobStatus:
        """Cancel an asynchronous video mask generation job."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support video mask generation")

    # --- Detection ---

    async def detection(
        self,
        input_data: DetectionInput,
        timeout: float = 60.0,
    ) -> DetectionResult:
        """Detect objects in an image using zero-shot detection."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support detection")

    # --- VLM ---

    async def vlm(
        self,
        input_data: VLMInput,
        timeout: float = 60.0,
    ) -> VLMResult:
        """Generate text conditioned on images."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support vlm")

    # --- Embedding ---

    async def embedding(
        self,
        input_data: EmbeddingInput,
        timeout: float = 60.0,
    ) -> EmbeddingResult:
        """Embed an image or text into a shared vector space (CLIP-style)."""
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support embedding")
