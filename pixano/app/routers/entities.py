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
    limit: int | None = None,
    skip: int = 0,
    where: str | None = None,
    item_ids: list[str] | None = Query(None),
) -> list[EntityModel]:
    """Get entities from a table of a dataset.

    They can be filtered by IDs, item IDs, a where clause or paginated.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        settings: App settings.
        ids: IDs of the views.
        limit: Limit number of views.
        skip: Skip number of views.
        where: Where clause.
        item_ids: Item IDs.

    Returns:
        List of views.
    """
    return await get_rows_handler(
        dataset_id=dataset_id,
        group=SchemaGroup.ENTITY,
        table=table,
        settings=settings,
        where=where,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
    )


@router.get("/{dataset_id}/{table}/{id}", response_model=EntityModel)
async def get_entity(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> EntityModel:
    """Get an entity from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the entity.
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
    """Add entities in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        entities: Entities to add.
        settings: App settings.

    Returns:
        List of entities added.
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
    """Add an entity in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the entity.
        entity: Entity to add.
        settings: App settings.

    Returns:
        The entity added.
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
    """Update an entity in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the entity.
        entity: Entity to update.
        settings: App settings.

    Returns:
        The entity updated.
    """
    return await update_row_handler(dataset_id, SchemaGroup.ENTITY, table, id, entity, settings)


@router.put("/{dataset_id}/{table}/", response_model=list[EntityModel])
async def update_entities(
    dataset_id: str,
    table: str,
    entities: list[EntityModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[EntityModel]:
    """Update entities in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        entities: Entities to update.
        settings: App settings.

    Returns:
        List of entities updated.
    """
    return await update_rows_handler(dataset_id, SchemaGroup.ENTITY, table, entities, settings)


@router.delete("/{dataset_id}/{table}/{id}")
async def delete_entity(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Delete an entity from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the entity to delete.
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
    """Delete entities from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        ids: IDs of the entities to delete.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, SchemaGroup.ENTITY, table, ids, settings)
