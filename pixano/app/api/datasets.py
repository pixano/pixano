# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pixano.app.settings import Settings, get_settings
from pixano.datasets import DatasetInfo


router = APIRouter(tags=["datasets"])


@router.get("/datasets", response_model=list[DatasetInfo])
async def get_datasets(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetInfo]:
    """Load dataset list.

    Args:
        settings (Settings): App settings

    Returns:
        list[DatasetInfo]: List of dataset infos
    """
    # Load datasets
    infos = DatasetInfo.load_directory(directory=settings.data_dir)

    # Return datasets
    if infos:
        return infos
    raise HTTPException(
        status_code=404,
        detail=f"No datasets found in {settings.data_dir.absolute()}",
    )
