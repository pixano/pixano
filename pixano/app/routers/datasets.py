# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pixano.app.models import DatasetModel
from pixano.app.settings import Settings, get_settings
from pixano.datasets import DatasetInfo

from .utils import get_dataset as get_dataset_utils


router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("/info", response_model=list[DatasetInfo])
async def get_datasets_info(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetInfo]:
    """Load dataset list.

    Args:
        settings: App settings

    Returns:
        List of dataset infos.
    """
    try:
        infos = DatasetInfo.load_directory(directory=settings.data_dir)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No datasets found in {settings.data_dir.absolute()}.",
        )

    if infos != []:
        return infos
    raise HTTPException(
        status_code=404,
        detail=f"No datasets found in {settings.data_dir.absolute()}.",
    )


@router.get("/info/{id}", response_model=DatasetInfo)
async def get_dataset_info(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetInfo]:
    """Load dataset list.

    Args:
        id: Dataset ID
        settings: App settings

    Returns:
        List of dataset infos.
    """
    try:
        infos = DatasetInfo.load_id(id, directory=settings.data_dir)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {id} not found in {settings.data_dir.absolute()}.",
        )

    return infos


@router.get("/{id}", response_model=DatasetModel)
async def get_dataset(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetModel:
    """Load dataset.

    Args:
        id: Dataset ID
        settings: App settings

    Returns:
        Dataset.
    """
    return DatasetModel.from_dataset(get_dataset_utils(id, settings.data_dir, None))
