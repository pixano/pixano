# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from pixano.app.settings import Settings, get_settings


router = APIRouter(prefix="/models", tags=["Models"])


@router.get("/", response_model=list[str])
async def get_models(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[str]:
    """Get all models in the models directory with the extension `.onnx`.

    Args:
        settings: App settings.

    Returns:
        List of models.
    """
    if settings.models_dir is None:
        raise HTTPException(status_code=500, detail="Models directory not set")
    models = [file.stem for file in settings.models_dir.glob("*.onnx")]
    return models


@router.get("/{model_name}", response_class=FileResponse)
async def get_model(
    model_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Get model file by name.

    The model file is expected to be in the models directory with the extension `.onnx`.

    Args:
        model_name: Model name.
        settings: App settings.

    Returns:
        Model file.
    """
    if settings.models_dir is None:
        raise HTTPException(status_code=500, detail="Models directory not set")
    model_path = settings.models_dir / f"{model_name}.onnx"
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found in {settings.models_dir}")
    return FileResponse(model_path)
