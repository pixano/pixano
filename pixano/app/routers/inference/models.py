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
    model_path: str | None = None
    model_class: str | None = None
    provider: str | None = None


class ServerInfoResponse(BaseModel):
    """Response model for server info."""

    app_name: str
    app_version: str
    app_description: str
    num_cpus: int | None
    num_gpus: int
    num_nodes: int
    gpus_used: list[int]
    gpu_to_model: dict[str, str]
    models: list[str]
    models_to_task: dict[str, str]


class ModelInfoWithProvider(BaseModel):
    """Response model for model info with provider name."""

    name: str
    task: str
    provider_name: str
    model_path: str | None = None
    model_class: str | None = None
    model_provider: str | None = None


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
            results.extend(
                ModelInfoWithProvider(
                    name=m.name,
                    task=m.task,
                    provider_name=provider_key,
                    model_path=m.model_path,
                    model_class=m.model_class,
                    model_provider=m.provider,
                )
                for m in models
            )
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

    return [
        ModelInfoResponse(
            name=m.name,
            task=m.task,
            model_path=m.model_path,
            model_class=m.model_class,
            provider=m.provider,
        )
        for m in models
    ]


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
        app_name=info.app_name,
        app_version=info.app_version,
        app_description=info.app_description,
        num_cpus=info.num_cpus,
        num_gpus=info.num_gpus,
        num_nodes=info.num_nodes,
        gpus_used=info.gpus_used,
        gpu_to_model=info.gpu_to_model,
        models=info.models,
        models_to_task=info.models_to_task,
    )
