# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pixano.app.models.items import ItemModel
from pixano.app.settings import Settings, get_settings
from pixano.features.schemas.schema_group import SchemaGroup

from .utils import (
    create_row_handler,
    create_rows_handler,
    delete_row_handler,
    delete_rows_handler,
    get_row_handler,
    get_rows_handler,
    update_row_handler,
    update_rows_handler,
)


router = APIRouter(prefix="/items", tags=["Items"])


@router.get("/{dataset_id}/", response_model=list[ItemModel])
async def get_items(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
    where: str | None = None,
) -> list[ItemModel]:
    """Get sources from the `'item'` table of a dataset.

    They can be filtered by IDs, a where clause or paginated.

    Args:
        dataset_id: Dataset ID containing the table.
        settings: App settings.
        ids: IDs of the sources.
        limit: Limit number of sources.
        skip: Skip number of sources.
        where: Where clause.

    Returns:
        List of sources.
    """
    return await get_rows_handler(
        dataset_id=dataset_id,
        group=SchemaGroup.ITEM,
        table=SchemaGroup.ITEM.value,
        settings=settings,
        where=where,
        ids=ids,
        item_ids=None,
        limit=limit,
        skip=skip,
    )


@router.get("/{dataset_id}/{id}", response_model=ItemModel)
async def get_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> ItemModel:
    """Get an item from the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        id: ID of the item.
        settings: App settings.

    Returns:
        The item.
    """
    return await get_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, settings)


@router.post("/{dataset_id}/", response_model=list[ItemModel])
async def create_items(
    dataset_id: str,
    items: list[ItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ItemModel]:
    """Add items in the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        items: Items to add.
        settings: App settings.

    Returns:
        List of items added.
    """
    return await create_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, items, settings)


@router.post("/{dataset_id}/{id}", response_model=ItemModel)
async def create_item(
    dataset_id: str,
    id: str,
    item: ItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemModel:
    """Add an item in the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        id: ID of the item.
        item: Item to add.
        settings: App settings.

    Returns:
        The item added.
    """
    return await create_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, item, settings)


@router.put("/{dataset_id}/{id}", response_model=ItemModel)
async def update_item(
    dataset_id: str,
    id: str,
    item: ItemModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ItemModel:
    """Update an item in the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        id: ID of the item.
        item: Item to update.
        settings: App settings.

    Returns:
        The item updated.
    """
    return await update_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, item, settings)


@router.put("/{dataset_id}/", response_model=list[ItemModel])
async def update_items(
    dataset_id: str,
    items: list[ItemModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ItemModel]:
    """Update items in the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        items: Items to update.
        settings: App settings.

    Returns:
        List of items updated.
    """
    return await update_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, items, settings)


@router.delete("/{dataset_id}/{id}")
async def delete_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete an item from the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        id: ID of the item to delete.
        settings: App settings.
    """
    return await delete_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, settings)


@router.delete("/{dataset_id}/")
async def delete_items(
    dataset_id: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete items from the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        ids: IDs of the items to delete.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, ids, settings)
