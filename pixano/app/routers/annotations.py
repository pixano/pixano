# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models.annotations import AnnotationModel
from pixano.app.settings import Settings, get_settings
from pixano.features.schemas.schema_group import SchemaGroup

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


router = APIRouter(prefix="/annotations", tags=["Annotations"])


@router.get("/{dataset_id}/{table}/", response_model=list[AnnotationModel])
async def get_annotations(
    dataset_id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    item_ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[AnnotationModel]:
    """Get annotations.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        settings: App settings.
        ids: IDs.
        item_ids: Item IDs.
        limit: Limit number of annotations.
        skip: Skip number of annotations.

    Returns:
        List of annotations.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    annotation_rows = get_rows(dataset, table, ids, item_ids, limit, skip)
    annotation_models = get_models_from_rows(table, AnnotationModel, annotation_rows)
    return annotation_models


@router.get("/{dataset_id}/{table}/{id}", response_model=AnnotationModel)
async def get_annotation(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> AnnotationModel:
    """Get an annotation.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.

    Returns:
        The annotation.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    annotation_row = get_row(dataset, table, id)
    annotation_model = get_model_from_row(table, AnnotationModel, annotation_row)
    return annotation_model


@router.post("/{dataset_id}/{table}/", response_model=list[AnnotationModel])
async def create_annotations(
    dataset_id: str,
    table: str,
    annotations: list[AnnotationModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AnnotationModel]:
    """Create annotations.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        annotations: Annotations.
        settings: App settings.

    Returns:
        List of annotations.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    annotations_rows = create_rows(dataset, table, annotations)
    annotations_models = get_models_from_rows(table, AnnotationModel, annotations_rows)
    return annotations_models


@router.post("/{dataset_id}/{table}/{id}", response_model=AnnotationModel)
async def create_annotation(
    dataset_id: str,
    table: str,
    id: str,
    annotation: AnnotationModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnnotationModel:
    """Create an annotation.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        annotation: Annotation.
        settings: App settings.

    Returns:
        The annotation.
    """
    if id != annotation.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    annotation_row = create_row(dataset, table, annotation)
    annotation_model = get_model_from_row(table, AnnotationModel, annotation_row)
    return annotation_model


@router.put("/{dataset_id}/{table}/{id}", response_model=AnnotationModel)
async def update_annotation(
    dataset_id: str,
    table: str,
    id: str,
    annotation: AnnotationModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnnotationModel:
    """Update an annotation.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        annotation: Annotation.
        settings: App settings.

    Returns:
        The annotation.
    """
    if id != annotation.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    annotation_row = update_row(dataset, table, annotation)
    annotation_model = get_model_from_row(table, AnnotationModel, annotation_row)
    return annotation_model


@router.put("/{dataset_id}/{table}/", response_model=list[AnnotationModel])
async def update_annotations(
    dataset_id: str,
    table: str,
    annotations: list[AnnotationModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AnnotationModel]:
    """Update annotations.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        annotations: Annotations.
        settings: App settings.

    Returns:
        List of annotations.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    annotation_rows = update_rows(dataset, table, annotations)
    annotation_models = get_models_from_rows(table, AnnotationModel, annotation_rows)
    return annotation_models


@router.delete("/{dataset_id}/{table}/{id}")
async def delete_annotation(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Delete an annotation.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    delete_row(dataset, table, id)
    return None


@router.delete("/{dataset_id}/{table}/")
async def delete_annotations(
    dataset_id: str,
    table: str,
    ids: list[str],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete annotations.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        ids: IDs.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, SchemaGroup.ANNOTATION)
    delete_rows(dataset, table, ids)
    return None
