# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pixano.app.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset


router = APIRouter(tags=["models"])


@router.get("/", response_model=list[str])
async def list_models(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[str]:
    """Load models.

    Returns:
        List of models.
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


@router.get(
    "/{model_id}",
    response_model=str,
)
async def get_model(  # noqa: D417
    ds_id: str,
    model_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:  # type: ignore
    """Load a model.

    Args:
        ds_id: Dataset ID
        model_id: Model ID (ONNX file path)
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        try:
            ...
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=("No model table in dataset"),
            )

        raise HTTPException(
            status_code=404,
            detail=(f"No model '{model_id}' found in dataset",),
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )
