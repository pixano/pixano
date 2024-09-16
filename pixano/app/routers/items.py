# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models.items import ItemModel
from pixano.app.settings import Settings, get_settings
from pixano.datasets.utils import DatasetAccessError, DatasetOffsetLimitError, DatasetPaginationError
from pixano.features.schemas.schema_group import SchemaGroup

from .utils import (
    assert_table_in_group,
    create_rows,
    delete_rows,
    get_dataset,
    get_models_from_rows,
    get_rows,
    update_rows,
)


router = APIRouter(prefix="/items", tags=["Items"])


@router.get("/{dataset_id}/", response_model=list[ItemModel])
async def get_items(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[ItemModel]:
    """Get items.

    Args:
        dataset_id: Dataset ID.
        settings: App settings.
        ids: IDs.
        limit: Limit number of items.
        skip: Skip number of items.

    Returns:
        List of items.
    """
    table = SchemaGroup.ITEM.value
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ITEM)
    try:
        item_rows = get_rows(dataset, table, ids, None, limit, skip)
    except DatasetOffsetLimitError as err:
        raise HTTPException(status_code=404, detail="Invalid query parameters. " + str(err))
    except DatasetPaginationError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except DatasetAccessError as err:
        raise HTTPException(status_code=500, detail=str(err))

    item_models = get_models_from_rows(table, ItemModel, item_rows)
    return item_models


@router.get("/{dataset_id}/{id}", response_model=ItemModel)
async def get_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> ItemModel:
    """Get an item.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        settings: App settings.

    Returns:
        The item.
    """
    return (await get_items(dataset_id, settings, ids=[id], limit=None, skip=0))[0]


@router.post("/{dataset_id}/", response_model=list[ItemModel])
async def create_items(
    dataset_id: str,
    items: list[ItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ItemModel]:
    """Create items.

    Args:
        dataset_id: Dataset ID.
        items: Items.
        settings: App settings.

    Returns:
        List of items.
    """
    table = SchemaGroup.ITEM.value
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ITEM)
    items_rows = create_rows(dataset, table, items)
    items_models = get_models_from_rows(table, ItemModel, items_rows)
    return items_models


@router.post("/{dataset_id}/{id}", response_model=ItemModel)
async def create_item(
    dataset_id: str,
    id: str,
    item: ItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemModel:
    """Create an item.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        item: Item.
        settings: App settings.

    Returns:
        The item.
    """
    if id != item.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    return (await create_items(dataset_id=dataset_id, items=[item], settings=settings))[0]


@router.put("/{dataset_id}/{id}", response_model=ItemModel)
async def update_item(
    dataset_id: str,
    id: str,
    item: ItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemModel:
    """Update an item.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        item: Item.
        settings: App settings.

    Returns:
        The item.
    """
    if id != item.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    return (await update_items(dataset_id=dataset_id, items=[item], settings=settings))[0]


@router.put("/{dataset_id}/", response_model=list[ItemModel])
async def update_items(
    dataset_id: str,
    items: list[ItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ItemModel]:
    """Update items.

    Args:
        dataset_id: Dataset ID.
        items: Items.
        settings: App settings.

    Returns:
        List of items.
    """
    table = SchemaGroup.ITEM.value
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ITEM)
    item_rows = update_rows(dataset, table, items)
    item_models = get_models_from_rows(table, ItemModel, item_rows)
    return item_models


@router.delete("/{dataset_id}/{id}")
async def delete_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete an item.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        settings: App settings.
    """
    return await delete_items(dataset_id, ids=[id], settings=settings)


@router.delete("/{dataset_id}/")
async def delete_items(
    dataset_id: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete items.

    Args:
        dataset_id: Dataset ID.
        ids: IDs.
        settings: App settings.
    """
    table = SchemaGroup.ITEM.value
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ITEM)
    delete_rows(dataset, table, ids)
    return None
