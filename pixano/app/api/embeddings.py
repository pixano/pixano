from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException

from pixano.app.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.features.schemas.embeddings.embedding import ViewEmbedding
from pixano.datasets.features.schemas.schema_group import _SchemaGroup


router = APIRouter(tags=["embeddings"])


@router.get("/", response_model=list[str])
async def list_embeddings(
    ds_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[str]:
    """List embeddings table.

    Returns:
        List of embeddings.
    """
    # Load list of embeddings
    dataset = Dataset.find(ds_id, settings.data_dir)
    if dataset:
        table_embeddings = list(dataset.schema._groups[_SchemaGroup.EMBEDDING])
        if len(table_embeddings) > 0:
            return table_embeddings
        raise HTTPException(
            status_code=404,
            detail=f"No embeddings found in dataset {ds_id}.",
        )
    raise HTTPException(
        status_code=404,
        detail=f"No dataset found in {settings.data_dir.absolute()}.",
    )


@router.get("/{embedding_name}", response_model=list[str])
def search_semantically_view(
    embedding_name: str,
    text: str,
    ds_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 20,
    offset: int = 0,
):
    """View semantic search.

    Args:
        embedding_name: Embedding table name.
        text: Text to search.
        ds_id: Dataset ID.
        settings: Settings.
        limit: Limit of results.
        offset: Offset of results.
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        try:
            embedding_table = dataset.open_table(embedding_name)
            results = (
                embedding_table.search(text)
                .limit(offset + limit)
                .to_pydantic(dataset.schema.schemas[embedding_name])[offset:]
            )
            if not results:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"No results found for query '{text}' in {embedding_name} with limit {limit} and offset "
                        f"{offset}."
                    ),
                )
            results = cast(list[ViewEmbedding], results)
            views = [dataset.resolve_ref(result.view_ref) for result in results]
            return views

        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=("No embeddings table in dataset."),
            )
    raise HTTPException(
        status_code=404,
        detail=f"No dataset found in {settings.data_dir.absolute()}.",
    )
