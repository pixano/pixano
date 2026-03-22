# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from datetime import datetime
from typing import Any

from ..exceptions import ProviderConnectionError
from ..registry import register_provider
from ..types import (
    CompressedRLEData,
    DetectionInput,
    DetectionOutput,
    DetectionResult,
    InferenceTask,
    ModelInfo,
    NDArrayData,
    ProviderCapabilities,
    SegmentationInput,
    SegmentationOutput,
    SegmentationResult,
    ServerInfo,
    TrackingInput,
    TrackingJobStatus,
    TrackingOutput,
    TrackingResult,
    UsageInfo,
    VLMInput,
    VLMOutput,
    VLMResult,
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
                InferenceTask.SEGMENTATION,
                InferenceTask.TRACKING,
                InferenceTask.DETECTION,
                InferenceTask.VLM,
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
                capability=m["capability"],
                model_path=m.get("model_path"),
                model_class=m.get("model_class"),
            )
            for m in models_data
        ]

        if task is not None:
            models = [m for m in models if m.capability == task.value]

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
            gpus_used=data.get("gpus_used", 0.0),
            gpu_to_model=data.get("gpu_to_model", {}),
            models=data.get("models", []),
            models_to_capability=data.get("models_to_capability", {}),
        )

    # --- Segmentation ---

    def _build_segmentation_request(self, input_data: SegmentationInput) -> dict[str, Any]:
        """Build request data for segmentation."""
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

        if input_data.mask_input is not None:
            request["mask_input"] = input_data.mask_input.to_dict()

        if input_data.points is not None:
            request["points"] = input_data.points

        if input_data.labels is not None:
            request["labels"] = input_data.labels

        if input_data.boxes is not None:
            request["boxes"] = input_data.boxes

        if input_data.return_logits:
            request["return_logits"] = input_data.return_logits

        return request

    def _build_binary_segmentation_request(
        self,
        input_data: SegmentationInput,
    ) -> list[tuple[str, tuple[str | None, bytes | str, str]]]:
        request = self._build_segmentation_request(input_data)
        image = request.pop("image")
        if not isinstance(image, bytes):
            raise TypeError("Binary segmentation requests require image bytes.")

        return [
            ("metadata", ("metadata.json", json.dumps(request), "application/json")),
            ("image", ("image.bin", image, "application/octet-stream")),
        ]

    def _parse_segmentation_response(self, response: dict[str, Any]) -> SegmentationResult:
        """Parse segmentation response."""
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

        mask_logits = None
        if data.get("mask_logits"):
            mask_logits = NDArrayData.from_dict(data["mask_logits"])

        output = SegmentationOutput(
            masks=masks,
            scores=scores,
            image_embedding=image_embedding,
            high_resolution_features=high_resolution_features,
            mask_logits=mask_logits,
        )

        return SegmentationResult(
            data=output,
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response["metadata"],
            id=response.get("id", ""),
            status=response.get("status", "SUCCESS"),
        )

    async def segmentation(
        self,
        input_data: SegmentationInput,
        timeout: float = 60.0,
    ) -> SegmentationResult:
        """Generate masks for an image."""
        if isinstance(input_data.image, bytes):
            response = await self.post(
                "inference/segmentation/binary",
                files=self._build_binary_segmentation_request(input_data),
                timeout=timeout,
            )
        else:
            request_data = self._build_segmentation_request(input_data)
            response = await self.post("inference/segmentation/", json=request_data, timeout=timeout)
        return self._parse_segmentation_response(response.json())

    # --- Tracking ---

    def _build_tracking_request(self, input_data: TrackingInput) -> dict[str, Any]:
        """Build request data for tracking."""
        request = {
            "model": input_data.model,
            "video": input_data.video,
            "objects_ids": list(input_data.objects_ids),
            "frame_indexes": list(input_data.frame_indexes),
            "propagate": input_data.propagate,
        }

        if input_data.points is not None:
            request["points"] = input_data.points

        if input_data.labels is not None:
            request["labels"] = input_data.labels

        if input_data.boxes is not None:
            request["boxes"] = input_data.boxes

        if input_data.interval is not None:
            request["interval"] = input_data.interval

        if input_data.keyframes is not None:
            request["keyframes"] = input_data.keyframes

        return request

    def _build_binary_tracking_request(
        self,
        input_data: TrackingInput,
    ) -> list[tuple[str, tuple[str | None, bytes | str, str]]]:
        request = self._build_tracking_request(input_data)
        video = request.pop("video")
        if not isinstance(video, list) or not all(isinstance(frame, bytes) for frame in video):
            raise TypeError("Binary tracking requests require a list of frame bytes.")

        files: list[tuple[str, tuple[str | None, bytes | str, str]]] = [
            ("metadata", ("metadata.json", json.dumps(request), "application/json")),
        ]
        for index, frame in enumerate(video):
            files.append(
                (
                    "frames",
                    (f"frame-{index:06d}.bin", frame, "application/octet-stream"),
                )
            )
        return files

    def _parse_tracking_response(self, response: dict[str, Any]) -> TrackingResult:
        """Parse tracking response."""
        data = response["data"]

        masks = [CompressedRLEData.from_dict(m) for m in data["masks"]]

        output = TrackingOutput(
            objects_ids=data["objects_ids"],
            frame_indexes=data["frame_indexes"],
            masks=masks,
        )

        return TrackingResult(
            data=output,
            status=response["status"],
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response["metadata"],
            id=response.get("id", ""),
        )

    def _parse_tracking_job_status(self, response: dict[str, Any]) -> TrackingJobStatus:
        data_payload = response.get("data")
        data = None
        if data_payload is not None:
            data = TrackingOutput(
                objects_ids=data_payload["objects_ids"],
                frame_indexes=data_payload["frame_indexes"],
                masks=[CompressedRLEData.from_dict(mask) for mask in data_payload["masks"]],
            )

        timestamp_value = response.get("timestamp")
        timestamp = datetime.fromisoformat(timestamp_value) if timestamp_value else None

        return TrackingJobStatus(
            job_id=response["job_id"],
            status=response["status"],
            detail=response.get("detail"),
            data=data,
            metadata=response.get("metadata", {}),
            timestamp=timestamp,
            processing_time=response.get("processing_time", 0.0),
        )

    async def tracking(
        self,
        input_data: TrackingInput,
        timeout: float = 120.0,
    ) -> TrackingResult:
        """Generate masks for video frames."""
        if isinstance(input_data.video, list) and any(isinstance(frame, bytes) for frame in input_data.video):
            response = await self.post(
                "inference/tracking/binary",
                files=self._build_binary_tracking_request(input_data),
                timeout=timeout,
            )
        else:
            request_data = self._build_tracking_request(input_data)
            response = await self.post("inference/tracking/", json=request_data, timeout=timeout)
        return self._parse_tracking_response(response.json())

    async def submit_tracking_job(
        self,
        input_data: TrackingInput,
        timeout: float = 30.0,
    ) -> TrackingJobStatus:
        """Submit an asynchronous tracking job."""
        if isinstance(input_data.video, list) and any(isinstance(frame, bytes) for frame in input_data.video):
            response = await self.post(
                "inference/tracking/jobs/binary",
                files=self._build_binary_tracking_request(input_data),
                timeout=timeout,
            )
        else:
            request_data = self._build_tracking_request(input_data)
            response = await self.post("inference/tracking/jobs/", json=request_data, timeout=timeout)
        return self._parse_tracking_job_status(response.json())

    async def get_tracking_job(
        self,
        job_id: str,
        timeout: float = 30.0,
    ) -> TrackingJobStatus:
        """Fetch asynchronous tracking job status."""
        response = await self.get(f"inference/tracking/jobs/{job_id}", timeout=timeout)
        return self._parse_tracking_job_status(response.json())

    async def cancel_tracking_job(
        self,
        job_id: str,
        timeout: float = 30.0,
    ) -> TrackingJobStatus:
        """Cancel an asynchronous tracking job."""
        response = await self.delete(f"inference/tracking/jobs/{job_id}", timeout=timeout)
        return self._parse_tracking_job_status(response.json())

    # --- Detection ---

    def _build_detection_request(self, input_data: DetectionInput) -> dict[str, Any]:
        """Build request data for zero-shot detection."""
        return {
            "model": input_data.model,
            "image": input_data.image,
            "classes": input_data.classes,
            "box_threshold": input_data.box_threshold,
            "text_threshold": input_data.text_threshold,
        }

    def _parse_detection_response(self, response: dict[str, Any]) -> DetectionResult:
        """Parse zero-shot detection response."""
        data = response["data"]

        output = DetectionOutput(
            boxes=data["boxes"],
            scores=data["scores"],
            classes=data["classes"],
        )

        return DetectionResult(
            data=output,
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response["metadata"],
            id=response.get("id", ""),
            status=response.get("status", "SUCCESS"),
        )

    async def detection(
        self,
        input_data: DetectionInput,
        timeout: float = 60.0,
    ) -> DetectionResult:
        """Detect objects using zero-shot detection."""
        request_data = self._build_detection_request(input_data)
        response = await self.post("inference/detection/", json=request_data, timeout=timeout)
        return self._parse_detection_response(response.json())

    # --- VLM ---

    def _build_vlm_request(self, input_data: VLMInput) -> dict[str, Any]:
        """Build request data for VLM inference."""
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

    def _parse_vlm_response(self, response: dict[str, Any]) -> VLMResult:
        """Parse VLM response."""
        data = response["data"]

        usage = UsageInfo(
            prompt_tokens=data["usage"]["prompt_tokens"],
            completion_tokens=data["usage"]["completion_tokens"],
            total_tokens=data["usage"]["total_tokens"],
        )

        output = VLMOutput(
            generated_text=data["generated_text"],
            usage=usage,
            generation_config=data.get("generation_config", {}),
        )

        return VLMResult(
            data=output,
            timestamp=datetime.fromisoformat(response["timestamp"]),
            processing_time=response["processing_time"],
            metadata=response.get("metadata", {}),
            id=response.get("id", ""),
            status=response.get("status", "SUCCESS"),
        )

    async def vlm(
        self,
        input_data: VLMInput,
        timeout: float = 60.0,
    ) -> VLMResult:
        """Generate text conditioned on images."""
        request_data = self._build_vlm_request(input_data)
        response = await self.post("inference/vlm/", json=request_data, timeout=timeout)
        return self._parse_vlm_response(response.json())
