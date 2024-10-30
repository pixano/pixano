# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pixano.app.models.views import ViewModel
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


router = APIRouter(prefix="/views", tags=["Views"])


@router.get("/{dataset_id}/{table}/", response_model=list[ViewModel])
async def get_views(
    dataset_id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
    where: str | None = None,
    item_ids: list[str] | None = Query(None),
) -> list[ViewModel]:
    """Get views.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        settings: App settings.
        ids: IDs.
        limit: Limit number of views.
        where: Where clause.
        skip: Skip number of views.
        item_ids: Item IDs.

    Returns:
        List of views.
    """
    return await get_rows_handler(
        dataset_id=dataset_id,
        group=SchemaGroup.VIEW,
        table=table,
        settings=settings,
        where=where,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
    )


@router.get("/{dataset_id}/{table}/{id}", response_model=ViewModel)
async def get_view(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> ViewModel:
    """Get a view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.

    Returns:
        The view.
    """
    return await get_row_handler(dataset_id, SchemaGroup.VIEW, table, id, settings)


@router.post("/{dataset_id}/{table}/", response_model=list[ViewModel])
async def create_views(
    dataset_id: str,
    table: str,
    views: list[ViewModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ViewModel]:
    """Create views.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        views: Views.
        settings: App settings.

    Returns:
        List of views.
    """
    return await create_rows_handler(dataset_id, SchemaGroup.VIEW, table, views, settings)


@router.post("/{dataset_id}/{table}/{id}", response_model=ViewModel)
async def create_view(
    dataset_id: str,
    table: str,
    id: str,
    view: ViewModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ViewModel:
    """Create a view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        view: View.
        settings: App settings.

    Returns:
        The view.
    """
    return await create_row_handler(dataset_id, SchemaGroup.VIEW, table, id, view, settings)


@router.put("/{dataset_id}/{table}/{id}", response_model=ViewModel)
async def update_view(
    dataset_id: str,
    table: str,
    id: str,
    view: ViewModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ViewModel:
    """Update a view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        view: View.
        settings: App settings.

    Returns:
        The view.
    """
    return await update_row_handler(dataset_id, SchemaGroup.VIEW, table, id, view, settings)


@router.put("/{dataset_id}/{table}/", response_model=list[ViewModel])
async def update_views(
    dataset_id: str,
    table: str,
    views: list[ViewModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ViewModel]:
    """Update views.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        views: Views.
        settings: App settings.

    Returns:
        List of views.
    """
    return await update_rows_handler(dataset_id, SchemaGroup.VIEW, table, views, settings)


@router.delete("/{dataset_id}/{table}/{id}")
async def delete_view(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Delete a view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.
    """
    return await delete_row_handler(dataset_id, SchemaGroup.VIEW, table, id, settings)


@router.delete("/{dataset_id}/{table}/")
async def delete_views(
    dataset_id: str,
    table: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete views.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        ids: IDs.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, SchemaGroup.VIEW, table, ids, settings)
