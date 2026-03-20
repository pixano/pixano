# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from pixano.api.settings import Settings, get_settings
from pixano.inference.exceptions import ProviderConnectionError, TaskNotSupportedError
from pixano.inference.provider import InferenceProvider
from pixano.inference.providers.pixano_inference import PixanoInferenceProvider
from pixano.inference.types import InferenceTask, ModelConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["Inference"])


# --- Response models ---


class ConnectedProviderResponse(BaseModel):
    name: str
    url: str | None = None


class InferenceStatusResponse(BaseModel):
    connected: bool
    providers: list[ConnectedProviderResponse]
    default: str | None = None


class ModelInfoResponse(BaseModel):
    name: str
    task: str
    model_path: str | None = None
    model_class: str | None = None


class ModelWithProviderResponse(ModelInfoResponse):
    provider_name: str


class InstantiateModelRequest(BaseModel):
    config: dict[str, Any]
    provider: str


class VLMRequest(BaseModel):
    model: str
    prompt: str | list[dict[str, Any]]
    images: list[str] | None = None
    max_new_tokens: int = 100
    temperature: float = 1.0


# --- Helpers ---


def _get_default_provider(settings: Settings) -> InferenceProvider:
    """Get the default inference provider from settings."""
    if not settings.inference_providers or not settings.default_inference_provider:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    provider = settings.inference_providers.get(settings.default_inference_provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    return provider


# --- Endpoints ---


@router.get("/status", response_model=InferenceStatusResponse, operation_id="get_inference_status")
def get_inference_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> InferenceStatusResponse:
    """Return the status of connected inference providers."""
    providers = []
    for name, provider in settings.inference_providers.items():
        url = getattr(provider, "url", None)
        providers.append(ConnectedProviderResponse(name=name, url=url))

    return InferenceStatusResponse(
        connected=len(providers) > 0,
        providers=providers,
        default=settings.default_inference_provider,
    )


@router.post("/connect", operation_id="connect_inference_provider")
async def connect_inference_provider(
    url: Annotated[str, Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Connect to an inference server at runtime."""
    try:
        provider = await PixanoInferenceProvider.connect(url)
    except ProviderConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    parsed = urlparse(url)
    provider_name = f"pixano-inference@{parsed.hostname}:{parsed.port or 80}"
    settings.inference_providers[provider_name] = provider
    settings.default_inference_provider = provider_name
    return {"status": "ok", "provider_name": provider_name}


@router.get("/models/list", response_model=list[ModelInfoResponse], operation_id="list_models")
async def list_models(
    settings: Annotated[Settings, Depends(get_settings)],
    task: Annotated[str | None, Query()] = None,
) -> list[ModelInfoResponse]:
    """List models from the default provider, optionally filtered by task."""
    provider = _get_default_provider(settings)
    inference_task = InferenceTask(task) if task else None
    models = await provider.list_models(task=inference_task)
    return [
        ModelInfoResponse(
            name=m.name,
            task=m.capability,
            model_path=m.model_path,
            model_class=m.model_class,
        )
        for m in models
    ]


@router.get(
    "/models/list-all", response_model=list[ModelWithProviderResponse], operation_id="list_all_models"
)
async def list_all_models(
    settings: Annotated[Settings, Depends(get_settings)],
    task: Annotated[str | None, Query()] = None,
) -> list[ModelWithProviderResponse]:
    """Aggregate models from all providers, adding provider_name field."""
    inference_task = InferenceTask(task) if task else None
    result: list[ModelWithProviderResponse] = []
    for name, provider in settings.inference_providers.items():
        try:
            models = await provider.list_models(task=inference_task)
            for m in models:
                result.append(
                    ModelWithProviderResponse(
                        name=m.name,
                        task=m.capability,
                        model_path=m.model_path,
                        model_class=m.model_class,
                        provider_name=name,
                    )
                )
        except Exception:
            logger.warning("Failed to list models from provider %s", name, exc_info=True)
    return result


@router.post("/models/instantiate", operation_id="instantiate_model")
async def instantiate_model(
    request: InstantiateModelRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Instantiate (load) a model on the default provider."""
    provider = _get_default_provider(settings)
    config = ModelConfig(
        name=request.config.get("name", ""),
        task=request.config.get("task", ""),
        path=request.config.get("path"),
        config=request.config.get("config", {}),
        processor_config=request.config.get("processor_config", {}),
    )
    try:
        await provider.instantiate_model(provider=request.provider, config=config)
    except TaskNotSupportedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok"}


@router.delete("/models/delete/{model_name}", operation_id="delete_model")
async def delete_model(
    model_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Delete (unload) a model on the default provider."""
    provider = _get_default_provider(settings)
    try:
        await provider.delete_model(model_name=model_name)
    except TaskNotSupportedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/tasks/conditional_generation/text-image", operation_id="conditional_generation_text_image")
async def conditional_generation_text_image(
    request: VLMRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Forward a VLM (text+image) generation request to the default provider."""
    from pixano.inference.types import VLMInput

    provider = _get_default_provider(settings)
    input_data = VLMInput(
        model=request.model,
        prompt=request.prompt,
        images=request.images,
        max_new_tokens=request.max_new_tokens,
        temperature=request.temperature,
    )
    result = await provider.vlm(input_data=input_data)
    return {
        "data": {
            "generated_text": result.data.generated_text,
            "usage": {
                "prompt_tokens": result.data.usage.prompt_tokens,
                "completion_tokens": result.data.usage.completion_tokens,
                "total_tokens": result.data.usage.total_tokens,
            },
            "generation_config": result.data.generation_config,
        },
        "timestamp": result.timestamp.isoformat(),
        "processing_time": result.processing_time,
        "metadata": result.metadata,
        "id": result.id,
        "status": result.status,
    }
