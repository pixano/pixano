# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models.entities import EntityModel
from pixano.app.settings import Settings, get_settings
from pixano.features.schemas.schema_group import _SchemaGroup

from .utils import (
    assert_table_in_group,
    create_row,
    create_rows,
    delete_row,
    delete_rows,
    get_dataset,
    get_model_from_row,
    get_models_from_rows,
    get_row,
    get_rows,
    update_row,
    update_rows,
)


router = APIRouter(prefix="/entities", tags=["Entities"])


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
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    entity_rows = get_rows(dataset, table, ids, item_ids, limit, skip)
    entity_models = get_models_from_rows(_SchemaGroup.ENTITY, table, EntityModel, entity_rows)
    return entity_models


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
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    entity_row = get_row(dataset, table, id)
    entity_model = get_model_from_row(_SchemaGroup.ENTITY, table, EntityModel, entity_row)
    return entity_model


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
        entities: Entities.
        settings: App settings.

    Returns:
        List of entities.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    entities_rows = create_rows(dataset, table, entities)
    entities_models = get_models_from_rows(_SchemaGroup.ENTITY, table, EntityModel, entities_rows)
    return entities_models


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
    if id != entity.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    entity_row = create_row(dataset, table, entity)
    entity_model = get_model_from_row(_SchemaGroup.ENTITY, table, EntityModel, entity_row)
    return entity_model


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
    if id != entity.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    entity_row = update_row(dataset, table, entity)
    entity_model = get_model_from_row(_SchemaGroup.ENTITY, table, EntityModel, entity_row)
    return entity_model


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
        entities: Entities.
        settings: App settings.

    Returns:
        List of entities.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    entity_rows = update_rows(dataset, table, entities)
    entity_models = get_models_from_rows(_SchemaGroup.ENTITY, table, EntityModel, entity_rows)
    return entity_models


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
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    delete_row(dataset, table, id)
    return None


@router.delete("/{dataset_id}/{table}/")
async def delete_entities(
    dataset_id: str,
    table: str,
    ids: list[str],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete entities.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        ids: IDs.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.ENTITY)
    delete_rows(dataset, table, ids)
    return None
