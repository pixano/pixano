# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from fastapi import HTTPException
from typing_extensions import TypeVar

from pixano.app.models import AnnotationModel, BaseSchemaModel, EmbeddingModel, EntityModel, ItemModel, ViewModel
from pixano.app.models.sources import SourceModel
from pixano.app.models.table_info import TableInfo
from pixano.app.models.utils import _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT
from pixano.app.settings import Settings
from pixano.datasets import Dataset
from pixano.datasets.utils import DatasetAccessError, DatasetOffsetLimitError, DatasetPaginationError
from pixano.features import BaseSchema, SchemaGroup
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.source import Source
from pixano.utils import get_super_type_from_dict


T = TypeVar("T", bound=BaseSchemaModel)


def get_dataset(dataset_id: str, dir: Path, media_dir: Path | None = None) -> Dataset:
    """Get a dataset.

    If the dataset is not found, raise a 404 error.

    Args:
        dataset_id: Dataset ID.
        dir: Directory containing the dataset.
        media_dir: Directory containing the media files.

    Returns:
        The dataset.
    """
    try:
        dataset = Dataset.find(dataset_id, dir, media_dir)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {dataset_id} not found in {dir.absolute()}.",
        )
    return dataset


def validate_group(
    group: str | SchemaGroup,
    valid_groups: set[SchemaGroup] = set(SchemaGroup),
) -> SchemaGroup:
    """Assert that a group is valid."""
    try:
        group = SchemaGroup(group)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Group {group} is not a SchemaGroup.",
        )
    if group not in valid_groups:
        raise HTTPException(
            status_code=400,
            detail=f"Group {group.value} is not valid.",
        )
    return group


def assert_table_in_group(dataset: Dataset, table: str, group: SchemaGroup) -> None:
    """Assert that a table belongs to a group.

    If the table does not belong to the group, raise a 404 error.

    Args:
        dataset: Dataset.
        table: Table name.
        group: Group.
    """
    if table in [SchemaGroup.ITEM.value, SchemaGroup.SOURCE.value]:
        return
    elif table not in dataset.schema.groups[group]:
        raise HTTPException(
            status_code=404,
            detail=f"Table {table} is not in the {group.value} group table.",
        )


def get_rows(
    dataset: Dataset,
    table: str,
    ids: list[str] | None = None,
    item_ids: list[str] | None = None,
    limit: int | None = None,
    skip: int = 0,
) -> list[BaseSchema]:
    """Get rows from a table.

    Args:
        dataset: Dataset.
        table: Table name.
        ids: IDs.
        item_ids: Item IDs.
        limit: Limit number of rows.
        skip: Skip number of rows.

    Returns:
        List of rows.
    """
    try:
        rows = dataset.get_data(table, ids, limit, skip, item_ids)
    except DatasetOffsetLimitError as err:
        raise HTTPException(status_code=404, detail="Invalid query parameters. " + str(err))
    except DatasetPaginationError as err:
        raise HTTPException(status_code=400, detail="Invalid query parameters. " + str(err))
    except DatasetAccessError as err:
        raise HTTPException(status_code=500, detail="Internal server error. " + str(err))

    if rows == [] or rows is None:
        raise HTTPException(
            status_code=404,
            detail=f"No rows found for {dataset.info.id}/{table}.",
        )
    return rows


def get_model_from_row(table: str, model_type: type[T], row: BaseSchema) -> T:
    """Get a model from a row.

    Args:
        group: Group.
        table: Table name.
        model_type: Model type.
        row: Row.

    Returns:
        The model.
    """
    try:
        is_group = issubclass(model_type, BaseSchemaModel)
        if not is_group:
            raise HTTPException(status_code=500, detail="Model type is not a subclass of BaseModelSchema.")
    except TypeError:
        raise HTTPException(status_code=500, detail="Model type is not a subclass of BaseModelSchema.")
    if issubclass(model_type, AnnotationModel):
        group = SchemaGroup.ANNOTATION
    elif issubclass(model_type, EmbeddingModel):
        group = SchemaGroup.EMBEDDING
    elif issubclass(model_type, EntityModel):
        group = SchemaGroup.ENTITY
    elif issubclass(model_type, ItemModel):
        group = SchemaGroup.ITEM
    elif issubclass(model_type, SourceModel):
        group = SchemaGroup.SOURCE
    elif issubclass(model_type, ViewModel):
        group = SchemaGroup.VIEW
    else:
        raise HTTPException(
            status_code=500,
            detail="Model type not correct.",
        )

    pixano_schema_type = get_super_type_from_dict(type(row), _PIXANO_SCHEMA_REGISTRY)

    if pixano_schema_type is None:
        raise HTTPException(
            status_code=500,
            detail="Schema type not found in registry.",
        )
    table_info = TableInfo(name=table, group=group.value, base_schema=pixano_schema_type.__name__)
    model = model_type.from_row(row, table_info)
    return model


def get_models_from_rows(
    table: str,
    model_type: type[T],
    rows: list[BaseSchema],
) -> list[T]:
    """Get models from rows.

    Args:
        table: Table name.
        model_type: Model type.
        rows: Rows.

    Returns:
        List of models.
    """
    return [get_model_from_row(table, model_type, row) for row in rows]


def delete_rows(
    dataset: Dataset,
    table: str,
    ids: list[str],
) -> list[str]:
    """Delete rows from a table.

    Args:
        dataset: Dataset.
        table: Table name.
        ids: IDs.

    Returns:
        IDs not found.
    """
    try:
        ids_not_found = dataset.delete_data(table, ids)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid query parameters. ids and item_ids cannot be set at the same time",
        )
    return ids_not_found


def update_rows(
    dataset: Dataset,
    table: str,
    models: list[BaseSchemaModel],
) -> list[BaseSchema]:
    """Update rows in a table.

    Args:
        dataset: Dataset.
        table: Table name.
        models: Models.

    Returns:
        The updated rows.
    """
    try:
        schema: type[BaseSchema] = dataset.schema.schemas[table] if table != SchemaGroup.SOURCE.value else Source
        rows: list[BaseSchema] = BaseSchemaModel.to_rows(models, schema)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.",
        )

    try:
        updated_rows = dataset.update_data(table, rows)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.",
        )

    # TODO: return updated rows instead of input rows
    # TODO: check if rows are updated or created which change HTTP status code
    return updated_rows


def create_rows(
    dataset: Dataset,
    table: str,
    models: list[BaseSchemaModel],
) -> list[BaseSchema]:
    """Add rows to a table.

    Args:
        dataset: Dataset.
        table: Table name.
        models: Models.

    Returns:
        The added rows.
    """
    try:
        schema: type[BaseSchema] = dataset.schema.schemas[table] if table != SchemaGroup.SOURCE.value else Source
        rows: list[BaseSchema] = BaseSchemaModel.to_rows(models, schema)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.",
        )

    try:
        created_rows = dataset.add_data(table, rows)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.",
        )

    return created_rows


async def get_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    settings: Settings,
    ids: list[str] | None = None,
    item_ids: list[str] | None = None,
    limit: int | None = None,
    skip: int = 0,
) -> list[BaseSchemaModel]:
    """Get row models.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        settings: App settings.
        ids: IDs.
        item_ids: Item IDs.
        limit: Limit number of rows.
        skip: Skip number of rows.

    Returns:
        List of models.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, group)
    rows = get_rows(dataset, table, ids, item_ids, limit, skip)
    models = get_models_from_rows(table, _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group], rows)
    return models


async def get_row_handler(
    dataset_id: str, group: SchemaGroup, table: str, id: str, settings: Settings
) -> BaseSchemaModel:
    """Get a row model.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        id: ID.
        settings: App settings.

    Returns:
        The model.
    """
    return (await get_rows_handler(dataset_id, group, table, settings, ids=[id], item_ids=None, limit=None, skip=0))[0]


async def create_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    rows: list[BaseSchemaModel],
    settings: Settings,
) -> list[BaseSchemaModel]:
    """Create rows.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        rows: Annotations.
        settings: App settings.

    Returns:
        List of rows.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, group)
    rows_rows = create_rows(dataset, table, rows)
    rows_models = get_models_from_rows(table, _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group], rows_rows)
    return rows_models


async def create_row_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    row: BaseSchemaModel,
    settings: Settings,
) -> BaseSchemaModel:
    """Create an row.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        id: ID.
        row: Annotation.
        settings: App settings.

    Returns:
        The row.
    """
    if id != row.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    return (await create_rows_handler(dataset_id=dataset_id, group=group, table=table, rows=[row], settings=settings))[
        0
    ]


async def update_row_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    row: BaseSchemaModel,
    settings: Settings,
) -> BaseSchemaModel:
    """Update an row.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        id: ID.
        row: Row.
        settings: App settings.

    Returns:
        The row.
    """
    if id != row.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    return (await update_rows_handler(dataset_id=dataset_id, group=group, table=table, rows=[row], settings=settings))[
        0
    ]


async def update_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    rows: list[BaseSchemaModel],
    settings: Settings,
) -> list[BaseSchemaModel]:
    """Update rows.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        rows: Rows.
        settings: App settings.

    Returns:
        List of rows.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, group)
    row_rows = update_rows(dataset, table, rows)
    row_models = get_models_from_rows(table, _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group], row_rows)
    return row_models


async def delete_row_handler(dataset_id: str, group: SchemaGroup, table: str, id: str, settings: Settings) -> None:
    """Delete an row.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        id: ID.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, group, table, ids=[id], settings=settings)


async def delete_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    ids: list[str],
    settings: Settings,
) -> None:
    """Delete rows.

    Args:
        dataset_id: Dataset ID.
        group: Schema group.
        table: Table name.
        ids: IDs.
        settings: App settings.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, group)
    delete_rows(dataset, table, ids)
    return None
