# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette.responses import Response

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


@router.get("/{dataset_id}", response_model=list[ItemModel], operation_id="list_items")
def get_items(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
    where: str | None = None,
) -> list[ItemModel]:
    """Get items from the `'item'` table of a dataset.

    They can be filtered by IDs, a where clause or paginated.

    Args:
        dataset_id: Dataset ID containing the table.
        settings: App settings.
        ids: IDs of the items.
        limit: Limit number of items.
        skip: Skip number of items.
        where: Where clause.

    Returns:
        List of items.
    """
    return get_rows_handler(
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


@router.get("/{dataset_id}/{id}", response_model=ItemModel, operation_id="get_item")
def get_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> ItemModel:
    """Get an item from the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        id: ID of the item.
        settings: App settings.

    Returns:
        The item.
    """
    return get_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, settings)


@router.post("/{dataset_id}", response_model=list[ItemModel], status_code=201, operation_id="create_items")
def create_items(
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
    return create_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, items, settings)


@router.post("/{dataset_id}/{id}", response_model=ItemModel, status_code=201, operation_id="create_item")
def create_item(
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
    return create_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, item, settings)


@router.put("/{dataset_id}/{id}", response_model=ItemModel, operation_id="update_item")
def update_item(
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
    return update_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, item, settings)


@router.put("/{dataset_id}", response_model=list[ItemModel], operation_id="update_items")
def update_items(
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
    return update_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, items, settings)


@router.delete("/{dataset_id}/{id}", status_code=204, response_class=Response, operation_id="delete_item")
def delete_item(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete an item from the `'item'` table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        id: ID of the item to delete.
        settings: App settings.
    """
    delete_row_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, id, settings)


@router.delete("/{dataset_id}", status_code=204, response_class=Response, operation_id="delete_items")
def delete_items(
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
    delete_rows_handler(dataset_id, SchemaGroup.ITEM, SchemaGroup.ITEM.value, ids, settings)
