# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import Depends
from pixano_inference.pydantic import ModelConfig
from pixano_inference.pydantic.models import ModelInfo

from pixano.app.routers.inference.utils import get_client_from_settings
from pixano.app.settings import Settings, get_settings

from .router import inference_router


@inference_router.get("/models/list", response_model=list[ModelInfo])
async def list_models(
    settings: Annotated[Settings, Depends(get_settings)], task: str | None = None
) -> list[ModelInfo]:
    """List all models from pixano inference client."""
    client = get_client_from_settings(settings)
    models = client.list_models()
    if task is None:
        return models
    return [m for m in models if task == m.task]


@inference_router.post("/models/instantiate")
async def instantiate_model(
    config: ModelConfig,
    provider: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ModelInfo:
    """Instantiate a model from pixano inference client."""
    client = get_client_from_settings(settings)
    return client.instantiate_model(provider=provider, config=config)


@inference_router.delete("/models/{model_name}")
async def delete_model(
    model_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete a model from pixano inference client."""
    client = get_client_from_settings(settings)
    return client.delete_model(model_name=model_name)
