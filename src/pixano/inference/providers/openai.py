# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""OpenAI-compatible inference providers.

This module provides a base class for OpenAI-compatible APIs and concrete
implementations for OpenAI, vLLM, and LM Studio.
"""

import base64
import mimetypes
import time
from abc import abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


class OpenAICompatibleProvider(HTTPProvider):
    """Base class for providers that implement the OpenAI-compatible API.

    Supports providers like OpenAI, vLLM, and LM Studio that expose
    ``/v1/models`` and ``/v1/chat/completions`` endpoints.
    """

    def __init__(self, url: str, api_key: str | None = None):
        super().__init__(url)
        self._api_key = api_key

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with auth header if api_key is set."""
        if self._client is None or self._client.is_closed:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0), headers=headers)
        return self._client

    @property
    @abstractmethod
    def name(self) -> str: ...

    async def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            tasks=[InferenceTask.VLM],
            supports_batching=False,
            supports_streaming=False,
        )

    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        if task is not None and task != InferenceTask.VLM:
            return []
        response = await self.get("/v1/models")
        data = response.json()
        return [
            ModelInfo(name=item["id"], capability="vlm")
            for item in data.get("data", [])
        ]

    async def get_server_info(self) -> ServerInfo:
        models = await self.list_models()
        return ServerInfo(
            app_name=self.name,
            app_version="unknown",
            app_description=f"{self.name} provider",
            num_cpus=None,
            num_gpus=0,
            num_nodes=1,
            gpus_used=0.0,
            gpu_to_model={},
            models=[m.name for m in models],
            models_to_capability={m.name: m.capability for m in models},
        )

    async def vlm(self, input_data: VLMInput, timeout: float = 60.0) -> VLMResult:
        messages = self._build_chat_messages(input_data)
        request_body: dict[str, Any] = {
            "model": input_data.model,
            "messages": messages,
            "max_tokens": input_data.max_new_tokens,
            "temperature": input_data.temperature,
        }

        start = time.monotonic()
        response = await self.post("/v1/chat/completions", json=request_body, timeout=timeout)
        processing_time = time.monotonic() - start

        data = response.json()
        choice = data["choices"][0]
        usage_data = data.get("usage", {})

        return VLMResult(
            data=VLMOutput(
                generated_text=choice["message"]["content"],
                usage=UsageInfo(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                ),
            ),
            timestamp=datetime.now(tz=timezone.utc),
            processing_time=processing_time,
            metadata={"model": input_data.model, "provider": self.name},
        )

    def _build_chat_messages(self, input_data: VLMInput) -> list[dict[str, Any]]:
        """Build OpenAI chat messages with optional vision content.

        When images are provided, they are injected into the last user message
        as multimodal content blocks alongside the text.
        """
        if isinstance(input_data.prompt, list):
            messages = [dict(m) for m in input_data.prompt]
            if input_data.images:
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        text = msg["content"]
                        msg["content"] = [
                            *[self._format_image(img) for img in input_data.images],
                            {"type": "text", "text": text},
                        ]
                        break
            return messages

        content: list[dict[str, Any]] = []

        if input_data.images:
            for image in input_data.images:
                content.append(self._format_image(image))

        content.append({"type": "text", "text": input_data.prompt})

        return [{"role": "user", "content": content}]

    @staticmethod
    def _format_image(image: str | Path) -> dict[str, Any]:
        """Format an image as an OpenAI vision content block."""
        image_str = str(image)

        if image_str.startswith("data:"):
            return {
                "type": "image_url",
                "image_url": {"url": image_str},
            }

        if image_str.startswith(("http://", "https://")):
            return {
                "type": "image_url",
                "image_url": {"url": image_str},
            }

        path = Path(image_str)
        if path.is_file():
            mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
            data = base64.b64encode(path.read_bytes()).decode("utf-8")
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{data}"},
            }

        # Assume base64-encoded data
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_str}"},
        }

    # --- Unsupported tasks ---

    async def segmentation(self, input_data: SegmentationInput, timeout: float = 60.0) -> SegmentationResult:
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support segmentation")

    async def tracking(self, input_data: TrackingInput, timeout: float = 120.0) -> TrackingResult:
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support tracking")

    async def submit_tracking_job(self, input_data: TrackingInput, timeout: float = 30.0) -> TrackingJobStatus:
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support tracking")

    async def get_tracking_job(self, job_id: str, timeout: float = 30.0) -> TrackingJobStatus:
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support tracking")

    async def cancel_tracking_job(self, job_id: str, timeout: float = 30.0) -> TrackingJobStatus:
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support tracking")

    async def detection(self, input_data: DetectionInput, timeout: float = 60.0) -> DetectionResult:
        raise TaskNotSupportedError(f"Provider '{self.name}' does not support detection")


@register_provider("openai")
class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, url: str = "https://api.openai.com"):
        super().__init__(url=url, api_key=api_key)

    @property
    def name(self) -> str:
        return "openai"


@register_provider("vllm")
class VLLMProvider(OpenAICompatibleProvider):
    """vLLM provider (OpenAI-compatible API)."""

    def __init__(self, url: str, api_key: str | None = None):
        super().__init__(url=url, api_key=api_key)

    @property
    def name(self) -> str:
        return "vllm"


@register_provider("lmstudio")
class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio provider (OpenAI-compatible API)."""

    def __init__(self, url: str, api_key: str | None = None):
        super().__init__(url=url, api_key=api_key)

    @property
    def name(self) -> str:
        return "lmstudio"
