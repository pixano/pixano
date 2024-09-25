# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pixano.app.models.embeddings import EmbeddingModel
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
    return await get_rows_handler(dataset_id, SchemaGroup.EMBEDDING, table, settings, ids, item_ids, limit, skip)


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
    return await get_row_handler(dataset_id, SchemaGroup.EMBEDDING, table, id, settings)


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
    return await create_rows_handler(dataset_id, SchemaGroup.EMBEDDING, table, embeddings, settings)


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
    return await create_row_handler(dataset_id, SchemaGroup.EMBEDDING, table, id, embedding, settings)


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
    return await update_row_handler(dataset_id, SchemaGroup.EMBEDDING, table, id, embedding, settings)


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
    return await update_rows_handler(dataset_id, SchemaGroup.EMBEDDING, table, embeddings, settings)


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
    return await delete_row_handler(dataset_id, SchemaGroup.EMBEDDING, table, id, settings)


@router.delete("/{dataset_id}/{table}/")
async def delete_embeddings(
    dataset_id: str,
    table: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete embeddings.

    Args:
        dataset_id: Dataset ID.
        table: Table name.
        ids: IDs.
        settings: App settings.
    """
    return await delete_rows_handler(dataset_id, SchemaGroup.EMBEDDING, table, ids, settings)
