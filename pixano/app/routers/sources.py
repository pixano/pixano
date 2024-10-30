# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pixano.app.models.sources import SourceModel
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


router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/{dataset_id}/", response_model=list[SourceModel])
async def get_sources(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
    where: str | None = None,
) -> list[SourceModel]:
    """Get sources.

    Args:
        dataset_id: Dataset ID.
        settings: App settings.
        ids: IDs.
        limit: Limit number of sources.
        skip: Skip number of sources.
        where: Where clause.

    Returns:
        List of sources.
    """
    return await get_rows_handler(
        dataset_id=dataset_id,
        group=SchemaGroup.SOURCE,
        table=SchemaGroup.SOURCE.value,
        settings=settings,
        where=where,
        ids=ids,
        item_ids=None,
        limit=limit,
        skip=skip,
    )


@router.get("/{dataset_id}/{id}", response_model=SourceModel)
async def get_source(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> SourceModel:
    """Get a source.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        settings: App settings.

    Returns:
        The source.
    """
    return await get_row_handler(dataset_id, SchemaGroup.SOURCE, SchemaGroup.SOURCE.value, id, settings)


@router.post("/{dataset_id}/", response_model=list[SourceModel])
async def create_sources(
    dataset_id: str,
    sources: list[SourceModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[SourceModel]:
    """Create sources.

    Args:
        dataset_id: Dataset ID.
        sources: Sources.
        settings: App settings.

    Returns:
        List of sources.
    """
    return await create_rows_handler(dataset_id, SchemaGroup.SOURCE, SchemaGroup.SOURCE.value, sources, settings)


@router.post("/{dataset_id}/{id}", response_model=SourceModel)
async def create_source(
    dataset_id: str,
    id: str,
    source: SourceModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SourceModel:
    """Create a source.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        source: Source.
        settings: App settings.

    Returns:
        The source.
    """
    return await create_row_handler(dataset_id, SchemaGroup.SOURCE, SchemaGroup.SOURCE.value, id, source, settings)


@router.put("/{dataset_id}/{id}", response_model=SourceModel)
async def update_source(
    dataset_id: str,
    id: str,
    source: SourceModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SourceModel:
    """Update a source.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        source: Source.
        settings: App settings.

    Returns:
        The source.
    """
    return await update_row_handler(dataset_id, SchemaGroup.SOURCE, SchemaGroup.SOURCE.value, id, source, settings)


@router.put("/{dataset_id}/", response_model=list[SourceModel])
async def update_sources(
    dataset_id: str,
    sources: list[SourceModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[SourceModel]:
    """Update sources.

    Args:
        dataset_id: Dataset ID.
        sources: Sources.
        settings: App settings.

    Returns:
        List of sources.
    """
    return await update_rows_handler(dataset_id, SchemaGroup.SOURCE, SchemaGroup.SOURCE.value, sources, settings)


@router.delete("/{dataset_id}/{id}")
async def delete_source(dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete a source.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        settings: App settings.
    """
    return await delete_row_handler(dataset_id, SchemaGroup.SOURCE, SchemaGroup.SOURCE.value, id, settings)


@router.delete("/{dataset_id}/")
async def delete_sources(
    dataset_id: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete sources.

    Args:
        dataset_id: Dataset ID.
        ids: IDs.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, SchemaGroup.SOURCE, SchemaGroup.SOURCE.value, ids, settings)
