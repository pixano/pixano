# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Google Gemini inference provider.

Uses the Google Generative AI REST API directly via httpx.
Authentication is via API key passed as a query parameter.
"""

import base64
import mimetypes
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx

from ..exceptions import TaskNotSupportedError
from ..registry import register_provider
from ..types import (
    DetectionInput,
    DetectionResult,
    InferenceTask,
    ModelInfo,
    ProviderCapabilities,
    SegmentationInput,
    SegmentationResult,
    ServerInfo,
    TrackingInput,
    TrackingJobStatus,
    TrackingResult,
    UsageInfo,
    VLMInput,
    VLMOutput,
    VLMResult,
)
from .base import HTTPProvider


@register_provider("gemini")
class GeminiProvider(HTTPProvider):
    """Google Gemini provider using the Generative AI REST API."""

    def __init__(self, api_key: str, url: str = "https://generativelanguage.googleapis.com"):
        super().__init__(url)
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "gemini"

    async def _request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        path: str,
        timeout: int | float = 60,
        **kwargs: Any,
    ) -> httpx.Response:
        """Inject API key as query parameter."""
        separator = "&" if "?" in path else "?"
        path = f"{path}{separator}key={self._api_key}"
        return await super()._request(method, path, timeout=timeout, **kwargs)

    async def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            tasks=[InferenceTask.VLM],
            supports_batching=False,
            supports_streaming=False,
        )

    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        if task is not None and task != InferenceTask.VLM:
            return []
        response = await self.get("/v1beta/models")
        data = response.json()
        models: list[ModelInfo] = []
        for model in data.get("models", []):
            methods = model.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                model_name = model["name"].removeprefix("models/")
                models.append(ModelInfo(name=model_name, capability="vlm"))
        return models

    async def get_server_info(self) -> ServerInfo:
        models = await self.list_models()
        return ServerInfo(
            app_name="gemini",
            app_version="unknown",
            app_description="Google Gemini provider",
            num_cpus=None,
            num_gpus=0,
            num_nodes=1,
            gpus_used=0.0,
            gpu_to_model={},
            models=[m.name for m in models],
            models_to_capability={m.name: m.capability for m in models},
        )

    async def vlm(self, input_data: VLMInput, timeout: float = 60.0) -> VLMResult:
        parts: list[dict[str, Any]] = []

        if input_data.images:
            for image in input_data.images:
                parts.append(self._format_image(image))

        prompt_text = input_data.prompt if isinstance(input_data.prompt, str) else str(input_data.prompt)
        parts.append({"text": prompt_text})

        request_body: dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": input_data.max_new_tokens,
                "temperature": input_data.temperature,
            },
        }

        start = time.monotonic()
        response = await self.post(
            f"/v1beta/models/{input_data.model}:generateContent",
            json=request_body,
            timeout=timeout,
        )
        processing_time = time.monotonic() - start

        data = response.json()
        candidate = data["candidates"][0]
        generated_text = candidate["content"]["parts"][0]["text"]
        usage_metadata = data.get("usageMetadata", {})

        return VLMResult(
            data=VLMOutput(
                generated_text=generated_text,
                usage=UsageInfo(
                    prompt_tokens=usage_metadata.get("promptTokenCount", 0),
                    completion_tokens=usage_metadata.get("candidatesTokenCount", 0),
                    total_tokens=usage_metadata.get("totalTokenCount", 0),
                ),
            ),
            timestamp=datetime.now(tz=timezone.utc),
            processing_time=processing_time,
            metadata={"model": input_data.model, "provider": "gemini"},
        )

    @staticmethod
    def _format_image(image: str | Path) -> dict[str, Any]:
        """Format an image as a Gemini inlineData part."""
        image_str = str(image)

        path = Path(image_str)
        if path.is_file():
            mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
            data = base64.b64encode(path.read_bytes()).decode("utf-8")
            return {"inlineData": {"mimeType": mime_type, "data": data}}

        # For URLs, Gemini doesn't support direct URLs in inlineData,
        # so we assume non-URL strings are base64-encoded data
        if image_str.startswith(("http://", "https://")):
            # Gemini supports fileData for URIs but for simplicity
            # we'll use the same base64 approach
            return {"inlineData": {"mimeType": "image/jpeg", "data": image_str}}

        # Assume base64-encoded data
        return {"inlineData": {"mimeType": "image/jpeg", "data": image_str}}

    # --- Unsupported tasks ---

    async def segmentation(self, input_data: SegmentationInput, timeout: float = 60.0) -> SegmentationResult:
        raise TaskNotSupportedError("Provider 'gemini' does not support segmentation")

    async def tracking(self, input_data: TrackingInput, timeout: float = 120.0) -> TrackingResult:
        raise TaskNotSupportedError("Provider 'gemini' does not support tracking")

    async def submit_tracking_job(self, input_data: TrackingInput, timeout: float = 30.0) -> TrackingJobStatus:
        raise TaskNotSupportedError("Provider 'gemini' does not support tracking")

    async def get_tracking_job(self, job_id: str, timeout: float = 30.0) -> TrackingJobStatus:
        raise TaskNotSupportedError("Provider 'gemini' does not support tracking")

    async def cancel_tracking_job(self, job_id: str, timeout: float = 30.0) -> TrackingJobStatus:
        raise TaskNotSupportedError("Provider 'gemini' does not support tracking")

    async def detection(self, input_data: DetectionInput, timeout: float = 60.0) -> DetectionResult:
        raise TaskNotSupportedError("Provider 'gemini' does not support detection")
