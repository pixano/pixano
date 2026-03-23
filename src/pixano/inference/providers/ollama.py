# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Ollama inference provider.

Uses the Ollama-native ``/api/tags`` for model listing and the
OpenAI-compatible ``/v1/chat/completions`` for VLM inference.
"""

from ..registry import register_provider
from ..types import InferenceTask, ModelInfo
from .openai import OpenAICompatibleProvider


@register_provider("ollama")
class OllamaProvider(OpenAICompatibleProvider):
    """Ollama provider."""

    def __init__(self, url: str = "http://localhost:11434", api_key: str | None = None):
        super().__init__(url=url, api_key=api_key)

    @property
    def name(self) -> str:
        return "ollama"

    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        if task is not None and task != InferenceTask.VLM:
            return []
        response = await self.get("/api/tags")
        data = response.json()
        return [
            ModelInfo(name=model["name"], capability="vlm")
            for model in data.get("models", [])
        ]
