# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pixano.app.models.entities import EntityModel
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


router = APIRouter(prefix="/entities", tags=["Entitys"])


@router.get("/{dataset_id}/{table}/", response_model=list[EntityModel])
async def get_entities(
    dataset_id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    item_ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[EntityModel]:
    """Get entities.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        settings: App settings.
        ids: IDs.
        item_ids: Item IDs.
        limit: Limit number of entities.
        skip: Skip number of entities.

    Returns:
        List of entities.
    """
    return await get_rows_handler(dataset_id, SchemaGroup.ENTITY, table, settings, ids, item_ids, limit, skip)


@router.get("/{dataset_id}/{table}/{id}", response_model=EntityModel)
async def get_entity(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> EntityModel:
    """Get an entity.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.

    Returns:
        The entity.
    """
    return await get_row_handler(dataset_id, SchemaGroup.ENTITY, table, id, settings)


@router.post("/{dataset_id}/{table}/", response_model=list[EntityModel])
async def create_entities(
    dataset_id: str,
    table: str,
    entities: list[EntityModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[EntityModel]:
    """Create entities.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        entities: Entitys.
        settings: App settings.

    Returns:
        List of entities.
    """
    return await create_rows_handler(dataset_id, SchemaGroup.ENTITY, table, entities, settings)


@router.post("/{dataset_id}/{table}/{id}", response_model=EntityModel)
async def create_entity(
    dataset_id: str,
    table: str,
    id: str,
    entity: EntityModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EntityModel:
    """Create an entity.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        entity: Entity.
        settings: App settings.

    Returns:
        The entity.
    """
    return await create_row_handler(dataset_id, SchemaGroup.ENTITY, table, id, entity, settings)


@router.put("/{dataset_id}/{table}/{id}", response_model=EntityModel)
async def update_entity(
    dataset_id: str,
    table: str,
    id: str,
    entity: EntityModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EntityModel:
    """Update an entity.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        entity: Entity.
        settings: App settings.

    Returns:
        The entity.
    """
    return await update_row_handler(dataset_id, SchemaGroup.ENTITY, table, id, entity, settings)


@router.put("/{dataset_id}/{table}/", response_model=list[EntityModel])
async def update_entities(
    dataset_id: str,
    table: str,
    entities: list[EntityModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[EntityModel]:
    """Update entities.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        entities: Entitys.
        settings: App settings.

    Returns:
        List of entities.
    """
    return await update_rows_handler(dataset_id, SchemaGroup.ENTITY, table, entities, settings)


@router.delete("/{dataset_id}/{table}/{id}")
async def delete_entity(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Delete an entity.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.
    """
    return await delete_row_handler(dataset_id, SchemaGroup.ENTITY, table, id, settings)


@router.delete("/{dataset_id}/{table}/")
async def delete_entities(
    dataset_id: str,
    table: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete entities.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        ids: IDs.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, SchemaGroup.ENTITY, table, ids, settings)
