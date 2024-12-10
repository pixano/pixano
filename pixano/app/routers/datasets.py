# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pixano.app.models import DatasetModel
from pixano.app.models.dataset_info import DatasetInfoModel
from pixano.app.settings import Settings, get_settings
from pixano.datasets import DatasetInfo
from pixano.datasets.utils.errors import DatasetAccessError

from .utils import get_dataset as get_dataset_utils


router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("/info", response_model=list[DatasetInfoModel])
async def get_datasets_info(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetInfoModel]:
    """Load a list of dataset information.

    Args:
        settings: App settings.

    Returns:
        List of dataset info.
    """
    try:
        infos_and_paths: list[tuple[DatasetInfo, Path]] = DatasetInfo.load_directory(
            directory=settings.library_dir, return_path=True
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No datasets found in {settings.library_dir.absolute()}.",
        )

    if len(infos_and_paths) > 0:
        return [DatasetInfoModel.from_dataset_info(info, path) for info, path in infos_and_paths]
    raise HTTPException(
        status_code=404,
        detail=f"No datasets found in {settings.library_dir.absolute()}.",
    )


@router.get("/info/{id}", response_model=DatasetInfoModel)
async def get_dataset_info(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetInfoModel:
    """Load a single dataset information.

    Args:
        id: Dataset ID to load info from.
        settings: App settings.

    Returns:
        The dataset info.
    """
    try:
        info, path = DatasetInfo.load_id(id, settings.library_dir, return_path=True)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {id} not found in {settings.library_dir.absolute()}.",
        )

    return DatasetInfoModel.from_dataset_info(info, path)


@router.get("/{id}", response_model=DatasetModel)
async def get_dataset(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetModel:
    """Load dataset from ID.

    Args:
        id: Dataset ID to load.
        settings: App settings.

    Returns:
        Dataset model.
    """
    return DatasetModel.from_dataset(get_dataset_utils(id, settings.library_dir, settings.media_dir))


@router.get("/{id}/{table}/count", response_model=int)
async def get_table_count(
    id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> int:
    """Get the number of rows in a table.

    Args:
        id: Dataset ID containing the table.
        table: Table name.
        settings: App settings.

    Returns:
        The number of rows in the table.
    """
    dataset = get_dataset_utils(id, settings.library_dir, settings.media_dir)
    try:
        db_table = dataset.open_table(table)
    except DatasetAccessError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    return db_table.count_rows()
