# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models.dataset_items import DatasetItemModel
from pixano.app.settings import Settings, get_settings

from .utils import get_dataset


router = APIRouter(prefix="/dataset_items", tags=["Dataset Items"])


@router.get("/{dataset_id}/", response_model=list[DatasetItemModel])
async def get_dataset_items(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = None,
    limit: int | None = None,
    skip: int = 0,
) -> list[DatasetItemModel]:
    """Get dataset items.

    Args:
        dataset_id: Dataset ID.
        settings: App settings.
        ids: IDs.
        limit: Limit number of dataset items.
        skip: Skip number of dataset items.

    Returns:
        List of dataset items.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)

    rows = dataset.get_dataset_items(ids, limit, skip)
    if rows == []:
        raise HTTPException(status_code=404, detail="Dataset items not found")

    return DatasetItemModel.from_dataset_items(rows, dataset.schema)


@router.get("/{dataset_id}/{id}", response_model=DatasetItemModel)
async def get_dataset_item(
    dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> DatasetItemModel:
    """Get dataset item.

    Args:
        dataset_id: Dataset ID.
        id: Dataset item ID.
        settings: App settings.

    Returns:
        Dataset item.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)

    row = dataset.get_dataset_items(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset item not found")

    return DatasetItemModel.from_dataset_item(row, dataset.schema)


@router.post("/{dataset_id}/", response_model=DatasetItemModel)
async def create_dataset_items(
    dataset_id: str,
    dataset_items: list[DatasetItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetItemModel]:
    """Create dataset items.

    Args:
        dataset_id: Dataset ID.
        dataset_items: Dataset items.
        settings: App settings.

    Returns:
        List of dataset items.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)

    rows = dataset.add_dataset_items(DatasetItemModel.to_dataset_items(dataset_items, dataset.schema))
    return DatasetItemModel.from_dataset_items(rows, dataset.schema)


@router.post("/{dataset_id}/{id}", response_model=DatasetItemModel)
async def create_dataset_item(
    dataset_id: str,
    id: str,
    dataset_item: DatasetItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetItemModel:
    """Create dataset item.

    Args:
        dataset_id: Dataset ID.
        id: Dataset item ID.
        dataset_item: Dataset item.
        settings: App settings.

    Returns:
        The dataset item.
    """
    if id != dataset_item.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")

    dataset = get_dataset(dataset_id, settings.data_dir, None)

    row = dataset.add_dataset_items(DatasetItemModel.to_dataset_item(dataset_item, dataset.schema))[0]
    return DatasetItemModel.from_dataset_item(row, dataset.schema)


@router.put("/{dataset_id}/", response_model=list[DatasetItemModel])
async def update_dataset_items(
    dataset_id: str,
    dataset_items: list[DatasetItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetItemModel]:
    """Update dataset items.

    Args:
        dataset_id: Dataset ID.
        dataset_items: Dataset items.
        settings: App settings.

    Returns:
        List of dataset items.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)

    rows = dataset.update_dataset_items(DatasetItemModel.to_dataset_items(dataset_items, dataset.schema))
    return DatasetItemModel.from_dataset_items(rows, dataset.schema)


@router.put("/{dataset_id}/{id}", response_model=DatasetItemModel)
async def update_dataset_item(
    dataset_id: str,
    id: str,
    dataset_item: DatasetItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetItemModel:
    """Update dataset item.

    Args:
        dataset_id: Dataset ID.
        id: Dataset item ID.
        dataset_item: Dataset item.
        settings: App settings.

    Returns:
        The dataset item.
    """
    if id != dataset_item.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")

    dataset = get_dataset(dataset_id, settings.data_dir, None)

    row = dataset.update_dataset_items(DatasetItemModel.to_dataset_item(dataset_item, dataset.schema))[0]
    return DatasetItemModel.from_dataset_item(row, dataset.schema)


@router.delete("/{dataset_id}/")
async def delete_dataset_items(
    dataset_id: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete dataset items.

    Args:
        dataset_id: Dataset ID.
        ids: IDs.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)

    dataset.delete_dataset_items(ids)
    return


@router.delete("/{dataset_id}/{id}")
async def delete_dataset_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete a dataset item.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)

    dataset.delete_dataset_items([id])
    return
