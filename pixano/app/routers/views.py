# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models.views import ViewModel
from pixano.app.settings import Settings, get_settings
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


router = APIRouter(prefix="/views", tags=["Views"])


@router.get("/{dataset_id}/{table}/", response_model=list[ViewModel])
async def get_views(
    dataset_id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    item_ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[ViewModel]:
    """Get views.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        settings: App settings.
        ids: IDs.
        item_ids: Item IDs.
        limit: Limit number of views.
        skip: Skip number of views.

    Returns:
        List of views.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.VIEW)
    view_rows = get_rows(dataset, table, ids, item_ids, limit, skip)
    view_models = get_models_from_rows(table, ViewModel, view_rows)
    return view_models


@router.get("/{dataset_id}/{table}/{id}", response_model=ViewModel)
async def get_view(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> ViewModel:
    """Get an view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.

    Returns:
        The view.
    """
    return (await get_views(dataset_id, table, settings, ids=[id], item_ids=None, limit=None, skip=0))[0]


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
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.VIEW)
    views_rows = create_rows(dataset, table, views)
    views_models = get_models_from_rows(table, ViewModel, views_rows)
    return views_models


@router.post("/{dataset_id}/{table}/{id}", response_model=ViewModel)
async def create_view(
    dataset_id: str,
    table: str,
    id: str,
    view: ViewModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ViewModel:
    """Create an view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        view: View.
        settings: App settings.

    Returns:
        The view.
    """
    if id != view.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    return (await create_views(dataset_id=dataset_id, table=table, views=[view], settings=settings))[0]


@router.put("/{dataset_id}/{table}/{id}", response_model=ViewModel)
async def update_view(
    dataset_id: str,
    table: str,
    id: str,
    view: ViewModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ViewModel:
    """Update an view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        view: View.
        settings: App settings.

    Returns:
        The view.
    """
    if id != view.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    return (await update_views(dataset_id=dataset_id, table=table, views=[view], settings=settings))[0]


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
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.VIEW)
    view_rows = update_rows(dataset, table, views)
    view_models = get_models_from_rows(table, ViewModel, view_rows)
    return view_models


@router.delete("/{dataset_id}/{table}/{id}")
async def delete_view(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Delete an view.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.
    """
    return await delete_views(dataset_id=dataset_id, table=table, ids=[id], settings=settings)


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
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.VIEW)
    delete_rows(dataset, table, ids)
    return None
