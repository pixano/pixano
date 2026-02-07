# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pixano.app.routers.inference.utils import get_provider_from_settings
from pixano.app.settings import Settings, get_settings
from pixano.inference import InferenceTask, ModelInfo


router = APIRouter(prefix="/models", tags=["Models"])


class ModelInfoResponse(BaseModel):
    """Response model for model info."""

    name: str
    task: str


class ServerInfoResponse(BaseModel):
    """Response model for server info."""

    version: str
    models_loaded: int
    num_gpus: int
    gpu_info: dict[str, Any]
    models: list[str]
    models_to_task: dict[str, str]
    ready: bool


class ModelInfoWithProvider(BaseModel):
    """Response model for model info with provider name."""

    name: str
    task: str
    provider_name: str


@router.get("/list-all", response_model=list[ModelInfoWithProvider])
async def list_all_models(
    settings: Annotated[Settings, Depends(get_settings)],
    task: str | None = None,
) -> list[ModelInfoWithProvider]:
    """List models from all connected providers.

    Args:
        settings: App settings.
        task: Optional task to filter models by.

    Returns:
        List of available models tagged with their provider name.
    """
    task_enum = None
    if task is not None:
        try:
            task_enum = InferenceTask(task)
        except ValueError:
            pass

    results: list[ModelInfoWithProvider] = []
    for provider_key, provider in settings.inference_providers.items():
        try:
            models: list[ModelInfo] = await provider.list_models(task=task_enum)
            if task is not None and task_enum is None:
                models = [m for m in models if m.task == task]
            results.extend(ModelInfoWithProvider(name=m.name, task=m.task, provider_name=provider_key) for m in models)
        except Exception:
            # Skip unreachable providers
            continue

    return results


@router.get("/list", response_model=list[ModelInfoResponse])
async def list_models(
    settings: Annotated[Settings, Depends(get_settings)],
    task: str | None = None,
    provider_name: str | None = None,
) -> list[ModelInfoResponse]:
    """List all models from the inference provider.

    Args:
        settings: App settings.
        task: Optional task to filter models by.
        provider_name: Optional provider name (uses default if not specified).

    Returns:
        List of available models.
    """
    provider = get_provider_from_settings(settings, provider_name)

    # Convert task string to InferenceTask enum if provided
    task_enum = None
    if task is not None:
        try:
            task_enum = InferenceTask(task)
        except ValueError:
            # Task might not match enum, try to filter by string
            pass

    models: list[ModelInfo] = await provider.list_models(task=task_enum)

    # If task_enum was None but task string was provided, filter by string
    if task is not None and task_enum is None:
        models = [m for m in models if m.task == task]

    return [ModelInfoResponse(name=m.name, task=m.task) for m in models]


@router.get("/server-info", response_model=ServerInfoResponse)
async def get_server_info(
    settings: Annotated[Settings, Depends(get_settings)],
    provider_name: str | None = None,
) -> ServerInfoResponse:
    """Get server information from the inference provider.

    Args:
        settings: App settings.
        provider_name: Optional provider name (uses default if not specified).

    Returns:
        Server information including version, GPU info, models, and readiness.
    """
    provider = get_provider_from_settings(settings, provider_name)

    try:
        info = await provider.get_server_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get server info: {e}")

    return ServerInfoResponse(
        version=info.version,
        models_loaded=info.models_loaded,
        num_gpus=info.num_gpus,
        gpu_info=info.gpu_info,
        models=info.models,
        models_to_task=info.models_to_task,
        ready=info.ready,
    )
