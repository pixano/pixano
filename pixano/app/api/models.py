# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pixano.app.settings import Settings, get_settings


router = APIRouter(tags=["models"])


@router.get("/models", response_model=list[str])
async def get_models(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[str]:
    """Load models.

    Returns:
        list[str]: List of models
    """
    # Load list of models
    models = []
    for model_path in settings.model_dir.glob("*.onnx"):
        models.append(model_path.name)

    # Return list of models
    if models:
        return models
    raise HTTPException(
        status_code=404,
        detail=f"No models found in {settings.model_dir.absolute()}",
    )
