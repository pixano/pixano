# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Explorer router: filter capability document, item navigation, semantic search."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from pixano.api.embeddings import submit_embedding_job
from pixano.api.models import (
    ColumnDescriptorResponse,
    FilterSchemaResponse,
    NeighborsResponse,
    SearchCapabilities,
)
from pixano.api.query import (
    FilterCompileError,
    build_column_catalogue,
    compile_filters,
    validate_sort,
)
from pixano.api.routers._deps import get_dataset_dep
from pixano.api.routers.data_io import _data_dir
from pixano.api.routers.records import _resolve_view_previews
from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset
from pixano.datasets.io.jobs import JobStore
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import EmbeddingInput


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Explorer"])


def _default_inference_provider(settings: Settings) -> InferenceProvider:
    if not settings.inference_providers or not settings.default_inference_provider:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    provider = settings.inference_providers.get(settings.default_inference_provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    return provider


class RecordSearchRequest(BaseModel):
    """Semantic search over records by text or by similarity to a record."""

    model: str | None = None
    text: str | None = None
    similar_to: str | None = None
    k: int = 50
    filter: list[str] | None = None
    where: str | None = None


class ComputeEmbeddingsRequest(BaseModel):
    """Start a record-embedding computation job."""

    model: str
    provider_name: str | None = None


class ComputeEmbeddingsResponse(BaseModel):
    """The launched embedding job."""

    job_id: str


class RecordSearchResponse(BaseModel):
    """Ranked semantic-search results."""

    items: list[dict[str, Any]]
    total: int
    model: str
    mode: str
    k: int


@router.get(
    "/filters",
    response_model=FilterSchemaResponse,
    response_model_exclude_none=True,
    operation_id="get_filter_schema",
    summary="Filter capability document",
    description="Publish the filterable/sortable columns, their operators and enumerable values, "
    "and the available search modes for the dataset's record table.",
)
def get_filter_schema(
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
) -> FilterSchemaResponse:
    """Return the explorer's filter/sort/search capability document."""
    catalogue = build_column_catalogue(dataset, "records")
    columns = [
        ColumnDescriptorResponse(
            name=column.name,
            type=column.type,
            collection=column.collection,
            source=column.source,
            filterable=column.filterable,
            sortable=column.sortable,
            searchable=column.searchable,
            indexed=column.indexed,
            operators=list(column.operators),
            values=list(column.values) if column.values is not None else None,
            values_complete=column.values_complete,
        )
        for column in catalogue
    ]
    # Lexical text search is always available; semantic search + the model that produced the
    # embeddings appear once a record-embedding table has been computed.
    modes = ["text"]
    models: list[str] = []
    if dataset.has_record_embeddings():
        modes.append("semantic")
        space = dataset.record_embedding_space() or {}
        model_id = space.get("model_id")
        if model_id:
            models.append(model_id)
    return FilterSchemaResponse(
        table="records", columns=columns, search=SearchCapabilities(modes=modes, models=models)
    )


@router.get(
    "/records/{record_id}/neighbors",
    response_model=NeighborsResponse,
    operation_id="get_record_neighbors",
    summary="Record neighbors",
    description="Locate a record within the current filtered, sorted result set and return its "
    "previous/next record ids, 1-based position, and the result-set total.",
)
def get_record_neighbors(
    dataset_id: str,
    record_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    filter: list[str] | None = Query(default=None),
    q: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    where: str | None = None,
) -> NeighborsResponse:
    """Return a record's neighbors within the explorer's active filter and sort."""
    catalogue = build_column_catalogue(dataset, "records")
    try:
        compiled_where, _referenced, _index_servable = compile_filters(catalogue, filter, q)
        sortcol, sort_order = validate_sort(catalogue, sort, order)
    except FilterCompileError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None

    if where:
        compiled_where = f"({where})" if compiled_where is None else f"{compiled_where} AND ({where})"

    try:
        neighbors = dataset.get_neighbors(
            record_id=record_id,
            table_name="records",
            where=compiled_where,
            sortcol=sortcol,
            order=sort_order,
        )
    except RuntimeError as err:
        # Only reachable via a malformed deprecated raw `where`.
        if where:
            raise HTTPException(status_code=400, detail=f"Invalid filter. {err}") from None
        raise
    return NeighborsResponse(**neighbors)


def _stored_record_vector(dataset: Dataset, record_id: str) -> list[float] | None:
    rows = dataset.get_data(dataset._RECORD_EMBEDDING_TABLE, where=f"record_id = '{record_id}'", limit=1)  # noqa: SLF001
    if not rows:
        return None
    return list(rows[0].vector)


def _prefilter_record_ids(dataset: Dataset, filters: list[str] | None, where: str | None) -> list[str] | None:
    if not filters and not where:
        return None
    catalogue = build_column_catalogue(dataset, "records")
    try:
        compiled_where, _referenced, _servable = compile_filters(catalogue, filters or [])
    except FilterCompileError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None
    if where:
        compiled_where = f"({where})" if compiled_where is None else f"{compiled_where} AND ({where})"
    matches = dataset.get_data("records", where=compiled_where, limit=None)
    return [record.id for record in (matches or [])]


@router.post(
    "/records/search",
    response_model=RecordSearchResponse,
    operation_id="search_records",
    summary="Semantic record search",
    description="Rank records by embedding similarity to a text query or to another record, "
    "optionally restricted by the explorer's structured filters.",
)
async def search_records(
    dataset_id: str,
    body: RecordSearchRequest,
    dataset: Dataset = Depends(get_dataset_dep),
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> RecordSearchResponse:
    """Semantic search over records (text→records or find-similar)."""
    if not dataset.has_record_embeddings():
        raise HTTPException(status_code=400, detail="No record embeddings; compute them first.")
    space = dataset.record_embedding_space() or {}
    model = body.model or space.get("model_id", "")

    mode: str
    if body.similar_to:
        query_vector = _stored_record_vector(dataset, body.similar_to)
        if query_vector is None:
            raise HTTPException(status_code=404, detail=f"Record '{body.similar_to}' has no embedding.")
        mode = "similar"
    elif body.text:
        provider = _default_inference_provider(settings)
        try:
            result = await provider.embedding(EmbeddingInput(model=model, text=body.text))
        except Exception as exc:  # noqa: BLE001 - provider/HTTP failure → 502
            raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}") from exc
        query_vector = list(result.data.embedding.values)
        mode = "text"
    else:
        raise HTTPException(status_code=400, detail="Provide either 'text' or 'similar_to'.")

    record_id_filter = _prefilter_record_ids(dataset, body.filter, body.where)
    try:
        records, distances = dataset.search_records(query_vector, k=body.k, record_id_filter=record_id_filter)
    except RuntimeError as err:
        raise HTTPException(status_code=400, detail=f"Search failed. {err}") from None

    record_ids = [record.id for record in records]
    previews = _resolve_view_previews(dataset_id, dataset, record_ids) if record_ids else {}
    items = [
        {
            **record.model_dump(),
            "_distance": distance,
            "view_previews": {name: preview.model_dump() for name, preview in (previews.get(record.id) or {}).items()}
            or None,
        }
        for record, distance in zip(records, distances, strict=True)
    ]
    return RecordSearchResponse(items=items, total=len(items), model=model, mode=mode, k=body.k)


@router.post(
    "/embeddings/compute",
    response_model=ComputeEmbeddingsResponse,
    status_code=202,
    operation_id="compute_record_embeddings",
    summary="Compute record embeddings",
    description="Launch a background job that embeds each record's image via the connected "
    "inference provider and builds the vector index. Poll it via GET /io/jobs/{id}.",
)
def compute_record_embeddings(
    dataset_id: str,
    body: ComputeEmbeddingsRequest,
    dataset: Dataset = Depends(get_dataset_dep),
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> ComputeEmbeddingsResponse:
    """Start the record-embedding computation job."""
    provider = (
        _default_inference_provider(settings)
        if body.provider_name is None
        else settings.inference_providers.get(body.provider_name)
    )
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown inference provider '{body.provider_name}'")
    store = JobStore.for_data_dir(_data_dir(settings))
    job_id = submit_embedding_job(store, dataset.path, dataset_id, provider, body.model)
    return ComputeEmbeddingsResponse(job_id=job_id)
