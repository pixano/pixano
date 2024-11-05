# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pixano.app.models.annotations import AnnotationModel
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


router = APIRouter(prefix="/annotations", tags=["Annotations"])


@router.get("/{dataset_id}/{table}/", response_model=list[AnnotationModel])
async def get_annotations(
    dataset_id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
    where: str | None = None,
    item_ids: list[str] | None = Query(None),
) -> list[AnnotationModel]:
    """Get annotations from a table of a dataset.

    They can be filtered by IDs, item IDs, a where clause or paginated.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        settings: App settings.
        ids: IDs of the annotations.
        limit: Limit number of annotations.
        skip: Skip number of annotations.
        where: Where clause.
        item_ids: Item IDs.

    Returns:
        List of annotations.
    """
    return await get_rows_handler(
        dataset_id=dataset_id,
        group=SchemaGroup.ANNOTATION,
        table=table,
        settings=settings,
        where=where,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
    )


@router.get("/{dataset_id}/{table}/{id}", response_model=AnnotationModel)
async def get_annotation(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> AnnotationModel:
    """Get an annotation from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the annotation.
        settings: App settings.

    Returns:
        The annotation.
    """
    return await get_row_handler(dataset_id, SchemaGroup.ANNOTATION, table, id, settings)


@router.post("/{dataset_id}/{table}/", response_model=list[AnnotationModel])
async def create_annotations(
    dataset_id: str,
    table: str,
    annotations: list[AnnotationModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AnnotationModel]:
    """Add annotations in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        annotations: Annotations to add.
        settings: App settings.

    Returns:
        List of annotations added.
    """
    return await create_rows_handler(dataset_id, SchemaGroup.ANNOTATION, table, annotations, settings)


@router.post("/{dataset_id}/{table}/{id}", response_model=AnnotationModel)
async def create_annotation(
    dataset_id: str,
    table: str,
    id: str,
    annotation: AnnotationModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnnotationModel:
    """Add an annotation in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the annotation.
        annotation: Annotation to add.
        settings: App settings.

    Returns:
        The annotation added.
    """
    return await create_row_handler(dataset_id, SchemaGroup.ANNOTATION, table, id, annotation, settings)


@router.put("/{dataset_id}/{table}/{id}", response_model=AnnotationModel)
async def update_annotation(
    dataset_id: str,
    table: str,
    id: str,
    annotation: AnnotationModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnnotationModel:
    """Update an annotation in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the annotation.
        annotation: Annotation to update.
        settings: App settings.

    Returns:
        The annotation updated.
    """
    return await update_row_handler(dataset_id, SchemaGroup.ANNOTATION, table, id, annotation, settings)


@router.put("/{dataset_id}/{table}/", response_model=list[AnnotationModel])
async def update_annotations(
    dataset_id: str,
    table: str,
    annotations: list[AnnotationModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AnnotationModel]:
    """Update annotations in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        annotations: Annotations to update.
        settings: App settings.

    Returns:
        List of annotations updated.
    """
    return await update_rows_handler(dataset_id, SchemaGroup.ANNOTATION, table, annotations, settings)


@router.delete("/{dataset_id}/{table}/{id}")
async def delete_annotation(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Delete an annotation from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the annotation to delete.
        settings: App settings.
    """
    return await delete_row_handler(dataset_id, SchemaGroup.ANNOTATION, table, id, settings)


@router.delete("/{dataset_id}/{table}/")
async def delete_annotations(
    dataset_id: str,
    table: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete annotations from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        ids: IDs of the annotations to delete.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, SchemaGroup.ANNOTATION, table, ids, settings)
