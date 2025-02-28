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
from pixano.datasets.utils import DatasetAccessError, DatasetPaginationError
from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.features import BaseSchema, SchemaGroup
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
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
    """Assert that a group is valid.

    Args:
        group: Group.
        valid_groups: The valid groups.
    """
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
    where: str | None = None,
    ids: list[str] | None = None,
    item_ids: list[str] | None = None,
    limit: int | None = None,
    skip: int = 0,
) -> list[BaseSchema]:
    """Get rows from a table.

    The rows can be filtered by a where clause, IDs, item IDs or a limit and a skip.

    Args:
        dataset: Dataset containing the table.
        table: Table name.
        where: Where clause.
        ids: IDs of the rows.
        item_ids: Item IDs of the rows.
        limit: Limit number of rows.
        skip: Skip number of rows.

    Returns:
        List of rows.
    """
    try:
        rows = dataset.get_data(table_name=table, where=where, ids=ids, limit=limit, skip=skip, item_ids=item_ids)
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
        table: Table name containing the row.
        model_type: Model type to create.
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
        table: Table name containing the rows.
        model_type: Model type to create.
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
        dataset: Dataset containing the table.
        table: Table name.
        ids: IDs of the rows to delete.

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
        dataset: Dataset containing the table.
        table: Table name.
        models: Models of the rows to update.

    Returns:
        The updated rows.
    """
    try:
        rows: list[BaseSchema] = BaseSchemaModel.to_rows(models, dataset)
    except Exception as err:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.\n" + str(err),
        )

    try:
        updated_rows = dataset.update_data(table, rows)
    except DatasetIntegrityError as err:
        raise HTTPException(status_code=400, detail="Dataset integrity compromised.\n" + str(err))
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.\n" + str(err),
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
        dataset: Dataset containing the table.
        table: Table name.
        models: Models of the rows to add.

    Returns:
        The added rows.
    """
    try:
        rows: list[BaseSchema] = BaseSchemaModel.to_rows(models, dataset)
    except Exception as err:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.\n" + str(err),
        )

    try:
        created_rows = dataset.add_data(table, rows)
    except DatasetIntegrityError as err:
        raise HTTPException(status_code=400, detail="Dataset integrity compromised.\n" + str(err))
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail="Invalid data.\n" + str(err),
        )

    return created_rows


async def get_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    settings: Settings,
    where: str | None = None,
    ids: list[str] | None = None,
    item_ids: list[str] | None = None,
    limit: int | None = None,
    skip: int = 0,
) -> list[BaseSchemaModel]:
    """Get row models.

    Rows can be filtered by a where clause, IDs, item IDs or a limit and a skip.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name.
        settings: App settings.
        where: Where clause.
        ids: IDs of the rows.
        item_ids: Item IDs of the rows.
        limit: Limit number of rows.
        skip: Skip number of rows.

    Returns:
        List of models.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.library_dir, settings.media_dir)
    assert_table_in_group(dataset, table, group)
    rows = get_rows(dataset=dataset, table=table, where=where, ids=ids, item_ids=item_ids, limit=limit, skip=skip)
    models = get_models_from_rows(table, _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group], rows)
    return models


async def get_row_handler(
    dataset_id: str, group: SchemaGroup, table: str, id: str, settings: Settings
) -> BaseSchemaModel:
    """Get a row model.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name.
        id: ID of the row.
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
    """Add rows to a table.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name containing the rows.
        rows: Rows to add.
        settings: App settings.

    Returns:
        List of updated rows.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.library_dir, settings.media_dir)
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
    """Add a row to a table.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name.
        id: ID of the row.
        row: Row to add.
        settings: App settings.

    Returns:
        The added row.
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
    """Update a row in a table.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name containing the row.
        id: ID of the row.
        row: Row to update.
        settings: App settings.

    Returns:
        The updated row.
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
    """Update rows in a table.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name containing the rows.
        rows: Rows to update.
        settings: App settings.

    Returns:
        List of updated rows.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.library_dir, settings.media_dir)
    assert_table_in_group(dataset, table, group)
    row_rows = update_rows(dataset, table, rows)
    row_models = get_models_from_rows(table, _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group], row_rows)
    return row_models


async def delete_row_handler(dataset_id: str, group: SchemaGroup, table: str, id: str, settings: Settings) -> None:
    """Delete a row from a table.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name containing the row.
        id: ID of the row to delete.
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
    """Delete rows from a table.

    Args:
        dataset_id: Dataset ID containing the table.
        group: Schema group of the schema of the table.
        table: Table name containing the rows.
        ids: IDs of the rows to delete.
        settings: App settings.
    """
    group = validate_group(group)
    dataset = get_dataset(dataset_id, settings.library_dir, settings.media_dir)
    assert_table_in_group(dataset, table, group)
    delete_rows(dataset, table, ids)
    return None
