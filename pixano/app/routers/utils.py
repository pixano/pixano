# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from fastapi import HTTPException
from typing_extensions import TypeVar

from pixano.app.models import AnnotationModel, BaseSchemaModel, EmbeddingModel, EntityModel, ItemModel, ViewModel
from pixano.app.models.table_info import TableInfo
from pixano.datasets import Dataset, DatasetPaginationError, DatasetAccessError
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


def assert_table_in_group(dataset: Dataset, table: str, group: SchemaGroup) -> None:
    """Assert that a table belongs to a group.

    If the table does not belong to the group, raise a 404 error.

    Args:
        dataset: Dataset.
        table: Table name.
        group: Group.
    """
    if table not in dataset.schema.groups[group]:
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
    except DatasetPaginationError as err:
        raise HTTPException(status_code=400,detail="Invalid query parameters. "+str(err))
    except DatasetAccessError as err:
        raise HTTPException(status_code=500,detail="Internal server error. "+str(err))
    
    if rows == [] or rows is None:
        raise HTTPException(
            status_code=404,
            detail=f"No rows found for {dataset.info.id}/{table}.",
        )
    return rows


def get_row(dataset: Dataset, table: str, id: str) -> BaseSchema:
    """Get a row from a table.

    If the row is not found, raise a 404 error.

    Args:
        dataset: Dataset.
        table: Table name.
        id: ID.

    Returns:
        The row.
    """
    return get_rows(dataset, table, [id], None, None, 0)[0]


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
            detail="Invalid query parameters.",
        )
    return ids_not_found


def delete_row(dataset: Dataset, table: str, id: str) -> bool:
    """Delete a row from a table.

    Args:
        dataset: Dataset.
        table: Table name.
        id: ID.

    Returns:
        Whether the row was found and deleted.
    """
    id_not_found = delete_rows(dataset, table, [id])
    return not (id_not_found == [])


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
        rows = BaseSchemaModel.to_rows(models, dataset.schema.schemas[table])
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


def update_row(
    dataset: Dataset,
    table: str,
    model: BaseSchemaModel,
) -> BaseSchema:
    """Update a row in a table.

    Args:
        dataset: Dataset.
        table: Table name.
        model: Model.

    Returns:
        The updated row.
    """
    updated_row = update_rows(dataset, table, [model])[0]
    return updated_row  # TODO: same as above, return updated row and change HTTP status code


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
        rows = BaseSchemaModel.to_rows(models, dataset.schema.schemas[table])
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


def create_row(
    dataset: Dataset,
    table: str,
    model: BaseSchemaModel,
) -> BaseSchema:
    """Add a row to a table.

    Args:
        dataset: Dataset.
        table: Table name.
        model: Model.

    Returns:
        The added row.
    """
    created_row = create_rows(dataset, table, [model])[0]
    return created_row
