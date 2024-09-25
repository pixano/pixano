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
    return await get_rows_handler(
        dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, settings, ids, None, limit, skip
    )


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
    return await get_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, settings)


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
    return await create_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, items, settings)


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
    return await create_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, item, settings)


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
    return await update_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, item, settings)


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
    return await update_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, items, settings)


@router.delete("/{dataset_id}/{id}")
async def delete_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete an item.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        settings: App settings.
    """
    return await delete_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, settings)


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
    return await delete_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, ids, settings)
