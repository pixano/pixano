# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from pixano_inference.pydantic import ModelConfig
from pixano_inference.pydantic.models import ModelInfo

from pixano.app.routers.inference.utils import get_client_from_settings
from pixano.app.settings import Settings, get_settings


router = APIRouter(prefix="/models", tags=["Models"])


@router.get("/list/", response_model=list[ModelInfo])
async def list_models(
    settings: Annotated[Settings, Depends(get_settings)], task: str | None = None
) -> list[ModelInfo]:
    """List all models from pixano inference client."""
    client = get_client_from_settings(settings)
    models = await client.list_models()
    if task is None:
        return models
    return [m for m in models if task == m.task]


@router.post("/instantiate")
async def instantiate_model(
    config: Annotated[ModelConfig, Body(embed=True)],
    provider: Annotated[str, Body(embed=True)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Instantiate a model from pixano inference client."""
    client = get_client_from_settings(settings)
    return await client.instantiate_model(provider=provider, config=config)


@router.delete("/delete/{model_name}")
async def delete_model(
    model_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete a model from pixano inference client."""
    client = get_client_from_settings(settings)
    return await client.delete_model(model_name=model_name)
