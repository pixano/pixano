# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models.embeddings import EmbeddingModel
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


router = APIRouter(prefix="/embeddings", tags=["Embeddings"])


@router.get("/{dataset_id}/{table}/", response_model=list[EmbeddingModel])
async def get_embeddings(
    dataset_id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    item_ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[EmbeddingModel]:
    """Get embeddings.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        settings: App settings.
        ids: IDs.
        item_ids: Item IDs.
        limit: Limit number of embeddings.
        skip: Skip number of embeddings.

    Returns:
        List of embeddings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    embedding_rows = get_rows(dataset, table, ids, item_ids, limit, skip)
    embedding_models = get_models_from_rows(_SchemaGroup.EMBEDDING, table, EmbeddingModel, embedding_rows)
    return embedding_models


@router.get("/{dataset_id}/{table}/{id}", response_model=EmbeddingModel)
async def get_embedding(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> EmbeddingModel:
    """Get an embedding.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.

    Returns:
        The embedding.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    embedding_row = get_row(dataset, table, id)
    embedding_model = get_model_from_row(_SchemaGroup.EMBEDDING, table, EmbeddingModel, embedding_row)
    return embedding_model


@router.post("/{dataset_id}/{table}/", response_model=list[EmbeddingModel])
async def create_embeddings(
    dataset_id: str,
    table: str,
    embeddings: list[EmbeddingModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[EmbeddingModel]:
    """Create embeddings.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        embeddings: Embeddings.
        settings: App settings.

    Returns:
        List of embeddings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    embeddings_rows = create_rows(dataset, table, embeddings)
    embeddings_models = get_models_from_rows(_SchemaGroup.EMBEDDING, table, EmbeddingModel, embeddings_rows)
    return embeddings_models


@router.post("/{dataset_id}/{table}/{id}", response_model=EmbeddingModel)
async def create_embedding(
    dataset_id: str,
    table: str,
    id: str,
    embedding: EmbeddingModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingModel:
    """Create an embedding.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        embedding: Embedding.
        settings: App settings.

    Returns:
        The embedding.
    """
    if id != embedding.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    embedding_row = create_row(dataset, table, embedding)
    embedding_model = get_model_from_row(_SchemaGroup.EMBEDDING, table, EmbeddingModel, embedding_row)
    return embedding_model


@router.put("/{dataset_id}/{table}/{id}", response_model=EmbeddingModel)
async def update_embedding(
    dataset_id: str,
    table: str,
    id: str,
    embedding: EmbeddingModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingModel:
    """Update an embedding.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        embedding: Embedding.
        settings: App settings.

    Returns:
        The embedding.
    """
    if id != embedding.id:
        raise HTTPException(status_code=400, detail="ID in path and body do not match.")
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    embedding_row = update_row(dataset, table, embedding)
    embedding_model = get_model_from_row(_SchemaGroup.EMBEDDING, table, EmbeddingModel, embedding_row)
    return embedding_model


@router.put("/{dataset_id}/{table}/", response_model=list[EmbeddingModel])
async def update_embeddings(
    dataset_id: str,
    table: str,
    embeddings: list[EmbeddingModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[EmbeddingModel]:
    """Update embeddings.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        embeddings: Embeddings.
        settings: App settings.

    Returns:
        List of embeddings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    embedding_rows = update_rows(dataset, table, embeddings)
    embedding_models = get_models_from_rows(_SchemaGroup.EMBEDDING, table, EmbeddingModel, embedding_rows)
    return embedding_models


@router.delete("/{dataset_id}/{table}/{id}")
async def delete_embedding(
    dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Delete an embedding.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        id: ID.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    delete_row(dataset, table, id)
    return None


@router.delete("/{dataset_id}/{table}/")
async def delete_embeddings(
    dataset_id: str,
    table: str,
    ids: list[str],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete embeddings.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        ids: IDs.
        settings: App settings.
    """
    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, table, _SchemaGroup.EMBEDDING)
    delete_rows(dataset, table, ids)
    return None
