# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime
from typing import Any

from ..exceptions import ProviderConnectionError
from ..registry import register_provider
from ..types import (
    CompressedRLEData,
    ImageMaskGenerationInput,
    ImageMaskGenerationOutput,
    ImageMaskGenerationResult,
    ImageZeroShotDetectionInput,
    ImageZeroShotDetectionOutput,
    ImageZeroShotDetectionResult,
    InferenceTask,
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
from .base import HTTPProvider


@register_provider("pixano-inference")
class PixanoInferenceProvider(HTTPProvider):
    """Provider for pixano-inference server.

    This provider communicates with a pixano-inference server using its HTTP API.
    It translates between Pixano's types and the pixano-inference API format.

    Example:
        ```python
        from pixano.inference import get_provider

        provider = get_provider("pixano-inference", url="http://localhost:8000")
        models = await provider.list_models()
        ```
    """

    @property
    def name(self) -> str:
        """Provider name."""
        return "pixano-inference"

    @classmethod
    async def connect(cls, url: str) -> "PixanoInferenceProvider":
        """Connect to a pixano-inference server.

        Args:
            url: The URL of the pixano-inference server.

        Returns:
            A connected PixanoInferenceProvider instance.

        Raises:
            ProviderConnectionError: If connection fails.
        """
        provider = cls(url=url)
        try:
            await provider.get("ready")
        except Exception:
            try:
                await provider.get("health")
            except Exception:
                try:
                    await provider.get("app/settings/")
                except Exception as e:
                    raise ProviderConnectionError(f"Failed to connect to pixano-inference at {url}: {e}") from e
        return provider

    async def get_capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        return ProviderCapabilities(
            tasks=[
                InferenceTask.MASK_GENERATION,
                InferenceTask.VIDEO_MASK_GENERATION,
                InferenceTask.OBJECT_DETECTION,
                InferenceTask.TEXT_GENERATION,
            ],
            supports_batching=True,
            supports_streaming=False,
        )

    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        """List available models."""
        response = await self.get("app/models/")
        models_data = response.json()
        models = [
            ModelInfo(
                name=m["name"],
                task=m["task"],
                model_path=m.get("model_path"),
                model_class=m.get("model_class"),
                provider=m.get("provider"),
            )
            for m in models_data
        ]

        if task is not None:
            models = [m for m in models if m.task == task.value]

        return models

    async def get_server_info(self) -> ServerInfo:
        """Get server information."""
        response = await self.get("app/settings/")
        data = response.json()
        return ServerInfo(
            app_name=data.get("app_name", ""),
            app_version=data.get("app_version", "unknown"),
            app_description=data.get("app_description", ""),
            num_cpus=data.get("num_cpus"),
            num_gpus=data.get("num_gpus", 0),
            num_nodes=data.get("num_nodes", 1),
            gpus_used=data.get("gpus_used", []),
            gpu_to_model=data.get("gpu_to_model", {}),
            models=data.get("models", []),
            models_to_task=data.get("models_to_task", {}),
        )

    # --- Mask Generation ---

    def _build_mask_request(self, input_data: ImageMaskGenerationInput) -> dict[str, Any]:
        """Build request data for mask generation."""
        request = {
            "model": input_data.model,
            "image": input_data.image,
            "reset_predictor": input_data.reset_predictor,
            "num_multimask_outputs": input_data.num_multimask_outputs,
            "multimask_output": input_data.multimask_output,
            "return_image_embedding": input_data.return_image_embedding,
        }

        if input_data.image_embedding is not None:
            request["image_embedding"] = input_data.image_embedding.to_dict()

        if input_data.high_resolution_features is not None:
            request["high_resolution_features"] = [f.to_dict() for f in input_data.high_resolution_features]

        if input_data.points is not None:
            request["points"] = input_data.points

        if input_data.labels is not None:
            request["labels"] = input_data.labels

        if input_data.boxes is not None:
            request["boxes"] = input_data.boxes

        return request

    def _parse_mask_response(self, response: dict[str, Any]) -> ImageMaskGenerationResult:
        """Parse mask generation response."""
        data = response["data"]

        # Parse masks
        masks = []
        for prompt_masks in data["masks"]:
            masks.append([CompressedRLEData.from_dict(m) for m in prompt_masks])

        # Parse scores
        scores = NDArrayData.from_dict(data["scores"])

        # Parse optional embeddings
        image_embedding = None
        if data.get("image_embedding"):
            image_embedding = NDArrayData.from_dict(data["image_embedding"])

        high_resolution_features = None
        if data.get("high_resolution_features"):
            high_resolution_features = [NDArrayData.from_dict(f) for f in data["high_resolution_features"]]

        output = ImageMaskGenerationOutput(
            masks=masks,
            scores=scores,
            image_embedding=image_embedding,
            high_resolution_features=high_resolution_features,
        )

        return ImageMaskGenerationResult(
            data=output,
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response["metadata"],
            id=response.get("id", ""),
            status=response.get("status", "SUCCESS"),
        )

    async def image_mask_generation(
        self,
        input_data: ImageMaskGenerationInput,
        timeout: float = 60.0,
    ) -> ImageMaskGenerationResult:
        """Generate masks for an image."""
        request_data = self._build_mask_request(input_data)
        response = await self.post("tasks/image/mask_generation/", json=request_data, timeout=timeout)
        return self._parse_mask_response(response.json())

    # --- Video Mask Generation ---

    def _build_video_mask_request(self, input_data: VideoMaskGenerationInput) -> dict[str, Any]:
        """Build request data for video mask generation."""
        request = {
            "model": input_data.model,
            "video": input_data.video,
            "objects_ids": list(input_data.objects_ids),
            "frame_indexes": list(input_data.frame_indexes),
        }

        if input_data.points is not None:
            request["points"] = input_data.points

        if input_data.labels is not None:
            request["labels"] = input_data.labels

        if input_data.boxes is not None:
            request["boxes"] = input_data.boxes

        return request

    def _parse_video_mask_response(self, response: dict[str, Any]) -> VideoMaskGenerationResult:
        """Parse video mask generation response."""
        data = response["data"]

        masks = [CompressedRLEData.from_dict(m) for m in data["masks"]]

        output = VideoMaskGenerationOutput(
            objects_ids=data["objects_ids"],
            frame_indexes=data["frame_indexes"],
            masks=masks,
        )

        return VideoMaskGenerationResult(
            data=output,
            status=response["status"],
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response["metadata"],
            id=response.get("id", ""),
        )

    async def video_mask_generation(
        self,
        input_data: VideoMaskGenerationInput,
        timeout: float = 120.0,
    ) -> VideoMaskGenerationResult:
        """Generate masks for video frames."""
        request_data = self._build_video_mask_request(input_data)
        response = await self.post("tasks/video/mask_generation/", json=request_data, timeout=timeout)
        return self._parse_video_mask_response(response.json())

    # --- Zero-Shot Detection ---

    def _build_detection_request(self, input_data: ImageZeroShotDetectionInput) -> dict[str, Any]:
        """Build request data for zero-shot detection."""
        return {
            "model": input_data.model,
            "image": input_data.image,
            "classes": input_data.classes,
            "box_threshold": input_data.box_threshold,
            "text_threshold": input_data.text_threshold,
        }

    def _parse_detection_response(self, response: dict[str, Any]) -> ImageZeroShotDetectionResult:
        """Parse zero-shot detection response."""
        data = response["data"]

        output = ImageZeroShotDetectionOutput(
            boxes=data["boxes"],
            scores=data["scores"],
            classes=data["classes"],
        )

        return ImageZeroShotDetectionResult(
            data=output,
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response["metadata"],
            id=response.get("id", ""),
            status=response.get("status", "SUCCESS"),
        )

    async def image_zero_shot_detection(
        self,
        input_data: ImageZeroShotDetectionInput,
        timeout: float = 60.0,
    ) -> ImageZeroShotDetectionResult:
        """Detect objects using zero-shot detection."""
        request_data = self._build_detection_request(input_data)
        response = await self.post("tasks/image/zero_shot_detection/", json=request_data, timeout=timeout)
        return self._parse_detection_response(response.json())

    # --- Text-Image Conditional Generation ---

    def _build_text_generation_request(self, input_data: TextImageConditionalGenerationInput) -> dict[str, Any]:
        """Build request data for text generation."""
        request: dict[str, Any] = {
            "model": input_data.model,
            "prompt": input_data.prompt,
            "max_new_tokens": input_data.max_new_tokens,
            "temperature": input_data.temperature,
        }

        if input_data.images is not None:
            request["images"] = [str(img) for img in input_data.images]
        else:
            request["images"] = None

        return request

    def _parse_text_generation_response(self, response: dict[str, Any]) -> TextImageConditionalGenerationResult:
        """Parse text generation response."""
        data = response["data"]

        usage = UsageInfo(
            prompt_tokens=data["usage"]["prompt_tokens"],
            completion_tokens=data["usage"]["completion_tokens"],
            total_tokens=data["usage"]["total_tokens"],
        )

        output = TextImageConditionalGenerationOutput(
            generated_text=data["generated_text"],
            usage=usage,
            generation_config=data.get("generation_config", {}),
        )

        return TextImageConditionalGenerationResult(
            data=output,
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response.get("metadata", {}),
            id=response.get("id", ""),
            status=response.get("status", "SUCCESS"),
        )

    async def text_image_conditional_generation(
        self,
        input_data: TextImageConditionalGenerationInput,
        timeout: float = 60.0,
    ) -> TextImageConditionalGenerationResult:
        """Generate text conditioned on images."""
        request_data = self._build_text_generation_request(input_data)
        response = await self.post(
            "tasks/multimodal/text-image/conditional_generation/", json=request_data, timeout=timeout
        )
        return self._parse_text_generation_response(response.json())
