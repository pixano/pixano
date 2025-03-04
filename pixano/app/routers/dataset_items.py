# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models.dataset_items import DatasetItemModel
from pixano.app.settings import Settings, get_settings
from pixano.datasets.dataset import DatasetAccessError, DatasetPaginationError

from .utils import get_dataset


router = APIRouter(prefix="/dataset_items", tags=["Dataset Items"])


@router.get("/{dataset_id}/", response_model=list[DatasetItemModel])
async def get_dataset_items(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[DatasetItemModel]:
    """Get dataset items from a dataset.

    Args:
        dataset_id: Dataset ID containing the items.
        settings: App settings.
        ids: IDs of the dataset items.
        limit: Limit number of dataset items.
        skip: Skip number of dataset items.

    Returns:
        List of dataset items.
    """
    dataset = get_dataset(dataset_id, settings.library_dir, None)

    try:
        rows = dataset.get_dataset_items(ids, limit, skip)
    except DatasetPaginationError as err:
        raise HTTPException(status_code=400, detail="Invalid query parameters. " + str(err))
    except DatasetAccessError as err:
        raise HTTPException(status_code=500, detail="Insternal server error. " + str(err))
    if rows == []:
        raise HTTPException(status_code=404, detail="Dataset items not found.")

    return DatasetItemModel.from_dataset_items(rows, dataset.schema)


@router.get("/{dataset_id}/{id}", response_model=DatasetItemModel)
async def get_dataset_item(
    dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> DatasetItemModel:
    """Get dataset item from a dataset.

    Args:
        dataset_id: Dataset ID.
        id: Dataset item ID.
        settings: App settings.

    Returns:
        The dataset item.
    """
    return (await get_dataset_items(dataset_id, settings, ids=[id]))[0]


@router.post("/{dataset_id}/", response_model=list[DatasetItemModel])
async def create_dataset_items(
    dataset_id: str,
    dataset_items: list[DatasetItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetItemModel]:
    """Add dataset items in a dataset.

    Args:
        dataset_id: Dataset ID to add the items.
        dataset_items: Dataset items to add.
        settings: App settings.

    Returns:
        List of dataset items added.
    """
    dataset = get_dataset(dataset_id, settings.library_dir, None)

    try:
        rows = dataset.add_dataset_items(DatasetItemModel.to_dataset_items(dataset_items, dataset))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset items")
    return DatasetItemModel.from_dataset_items(rows, dataset.schema)


@router.post("/{dataset_id}/{id}", response_model=DatasetItemModel)
async def create_dataset_item(
    dataset_id: str,
    id: str,
    dataset_item: DatasetItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetItemModel:
    """Add a dataset item.

    Args:
        dataset_id: Dataset ID to add the item.
        id: Dataset item ID to add.
        dataset_item: Dataset item.
        settings: App settings.

    Returns:
        The dataset item added.
    """
    if id != dataset_item.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")

    return (await create_dataset_items(dataset_id, [dataset_item], settings))[0]


@router.put("/{dataset_id}/", response_model=list[DatasetItemModel])
async def update_dataset_items(
    dataset_id: str,
    dataset_items: list[DatasetItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetItemModel]:
    """Update dataset items in a dataset.

    Args:
        dataset_id: Dataset ID containing the items.
        dataset_items: Dataset items to update.
        settings: App settings.

    Returns:
        List of dataset items updated.
    """
    dataset = get_dataset(dataset_id, settings.library_dir, None)

    try:
        rows = dataset.update_dataset_items(DatasetItemModel.to_dataset_items(dataset_items, dataset))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset items")
    return DatasetItemModel.from_dataset_items(rows, dataset.schema)


@router.put("/{dataset_id}/{id}", response_model=DatasetItemModel)
async def update_dataset_item(
    dataset_id: str,
    id: str,
    dataset_item: DatasetItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetItemModel:
    """Update dataset item in a dataset.

    Args:
        dataset_id: Dataset ID containing the item.
        id: Dataset item ID to update.
        dataset_item: Dataset item.
        settings: App settings.

    Returns:
        The dataset item updated.
    """
    if id != dataset_item.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")

    return (await update_dataset_items(dataset_id, [dataset_item], settings))[0]


@router.delete("/{dataset_id}/")
async def delete_dataset_items(
    dataset_id: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete dataset items from a dataset.

    Args:
        dataset_id: Dataset ID containing the items.
        ids: IDs of the dataset items to delete.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.library_dir, None)

    dataset.delete_dataset_items(ids)
    return


@router.delete("/{dataset_id}/{id}")
async def delete_dataset_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete a dataset item from a dataset.

    Args:
        dataset_id: Dataset ID containing the item.
        id: ID of the dataset item to delete.
        settings: App settings.
    """
    return await delete_dataset_items(dataset_id, ids=[id], settings=settings)
