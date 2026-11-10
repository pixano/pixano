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
    EmbeddingSpaceStatus,
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
from pixano.datasets.utils.errors import DatasetAccessError
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import EmbeddingInput, InferenceTask
from pixano.utils.python import to_sql_list


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Explorer"])


def _default_inference_provider(settings: Settings) -> InferenceProvider:
    if not settings.inference_providers or not settings.default_inference_provider:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    provider = settings.inference_providers.get(settings.default_inference_provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    return provider


class RecordSearchRequest(BaseModel):
    """Semantic search over records by text or by similarity to a record.

    ``model`` names the embeddings searched — a model's name, or its space's id —; the dataset's
    default ones when None. A text is embedded by that very model.
    """

    model: str | None = None
    text: str | None = None
    similar_to: str | None = None
    k: int = 50
    filter: list[str] | None = None
    where: str | None = None


class ComputeEmbeddingsRequest(BaseModel):
    """Start a record-embedding computation job.

    The model's vectors go to its own space, beside the other models'. ``force`` empties that
    model's space first — to compute it again from nothing, or to repair it —, or every model's
    when the dataset's `embeddings.json` cannot be read entirely.
    """

    model: str
    provider_name: str | None = None
    force: bool = False


class ComputeEmbeddingsResponse(BaseModel):
    """The launched embedding job."""

    job_id: str


class RecordSearchResponse(BaseModel):
    """Ranked semantic-search results, and the embeddings — the model, its space — they were found in."""

    items: list[dict[str, Any]]
    total: int
    model: str
    mode: str
    k: int
    space: str


class DefaultEmbeddingSpaceRequest(BaseModel):
    """The space a search naming no model reads from now on."""

    space_id: str


# What a search can read: the healths of a space that holds vectors to rank.
_SEARCHABLE = ("ready", "partial")
# What a computation goes on from without force: no embeddings yet, or vectors to add to.
_COMPUTABLE = (*_SEARCHABLE, "absent")


def _space_status(
    dataset: Dataset, space: dict[str, Any], health: dict[str, Any] | None = None
) -> EmbeddingSpaceStatus:
    """A space as the explorer shows it, with its health.

    Args:
        dataset: The dataset holding it.
        space: The space, as `Dataset.record_embedding_spaces` lists it.
        health: Its health (`Dataset.record_embedding_health`), when read already; read when None.

    Returns:
        The space, and its health.
    """
    health = health if health is not None else dataset.record_embedding_health(space["id"])
    return EmbeddingSpaceStatus(
        id=space["id"],
        model_id=space["model_id"],
        checkpoint=space["checkpoint"],
        dim=space["dim"],
        default=space["default"],
        status=str(health["status"]),
        detail=health["detail"],
        embedded_rows=int(health["embedded_media"]),
    )


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
    # Lexical text search is always available; semantic search once the default embeddings — those a
    # search naming no model reads — are healthy. A degraded store (missing or corrupt table, a
    # dimension mismatch) is reported in `status`, so that the UI offers a repair instead of a search
    # box that fails. Every space is listed with its health, read once each — a read growing with its
    # vectors —, the media counted once for all.
    held = dataset.record_embedding_spaces()
    default = next((space["id"] for space in held if space["default"]), None)
    health = dataset.record_embedding_health(default)
    healths = {space["id"]: health if space["id"] == default else None for space in held}
    for identifier in healths:
        healths[identifier] = healths[identifier] or dataset.record_embedding_health(identifier, media=health["media"])
    spaces = [_space_status(dataset, space, healths[space["id"]]) for space in held]
    modes = ["text", "semantic"] if health["status"] in _SEARCHABLE else ["text"]
    names = dict.fromkeys(space["model_id"] for space in sorted(held, key=lambda space: not space["default"]))
    models = [name for name in names if _searched_by(dataset, name, healths) in _SEARCHABLE]
    return FilterSchemaResponse(
        table="records",
        columns=columns,
        search=SearchCapabilities(
            modes=modes,
            models=models,
            status=str(health["status"]),
            detail=health["detail"],
            embedded_rows=int(health["embedded_media"]),
            total_records=int(health["records"]),
            total_media=int(health["media"]),
            spaces=spaces,
            fully_read=dataset.record_embeddings_fully_read(),
        ),
    )


def _searched_by(dataset: Dataset, name: str, healths: dict[str, Any]) -> str:
    """The health of the space a search naming this model reads — the default one of its name, or the first."""
    space = dataset.record_embedding_space(name)
    return str(healths[space["id"]]["status"]) if space is not None else "absent"


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


def _stored_record_vectors(dataset: Dataset, record_id: str, table: str) -> list[list[float]]:
    """Every vector of a record in a space's table, one per medium: a record is similar through any."""
    rows = dataset.get_data(table, where=f"record_id IN {to_sql_list(record_id)}", limit=None)
    return [list(row.vector) for row in rows]


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
    """Semantic search over records (text→records or find-similar), in the embeddings of the model named."""
    space = dataset.record_embedding_space(body.model or None)
    # Health short-circuit: a broken embedding store must yield an actionable error, never a 500.
    health = dataset.record_embedding_health(space["id"] if space is not None else None)
    if space is None and body.model:
        raise HTTPException(status_code=400, detail=f"No embeddings of model '{body.model}'; compute them first.")
    if space is None and health["status"] == "absent":
        raise HTTPException(status_code=400, detail="No record embeddings; compute them first.")
    if space is None or health["status"] in ("missing_table", "corrupt", "empty"):
        raise HTTPException(
            status_code=503,
            detail=f"Record embeddings are unavailable ({health['detail']}) Recompute the embeddings.",
        )
    if health["status"] == "dim_mismatch":
        raise HTTPException(
            status_code=409,
            detail=f"Record embeddings are stale ({health['detail']}) Recompute the embeddings.",
        )
    model = space["model_id"]

    mode: str
    if body.similar_to:
        try:
            query_vectors = _stored_record_vectors(dataset, body.similar_to, space["table"])
        except Exception as exc:  # noqa: BLE001 - corrupt storage → actionable 503
            raise HTTPException(
                status_code=503,
                detail=f"Record embeddings could not be read ({exc}). Recompute the embeddings.",
            ) from exc
        if not query_vectors:
            raise HTTPException(status_code=404, detail=f"Record '{body.similar_to}' has no embedding.")
        mode = "similar"
    elif body.text:
        provider = _default_inference_provider(settings)
        await _refuse_other_weights(provider, space)
        try:
            result = await provider.embedding(EmbeddingInput(model=model, text=body.text))
        except Exception as exc:  # noqa: BLE001 - provider/HTTP failure → 502
            raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}") from exc
        query_vectors = [list(result.data.embedding.values)]
        mode = "text"
    else:
        raise HTTPException(status_code=400, detail="Provide either 'text' or 'similar_to'.")

    query_dim = len(query_vectors[0])
    if query_dim != int(space["dim"]):
        raise HTTPException(
            status_code=409,
            detail=(
                f"The query embedding has dim {query_dim} but the stored embeddings have "
                f"dim {space['dim']} (model '{model}'). Recompute the embeddings "
                "with the current model."
            ),
        )

    record_id_filter = _prefilter_record_ids(dataset, body.filter, body.where)
    try:
        records, distances = dataset.search_records(
            query_vectors, k=body.k, record_id_filter=record_id_filter, model=space["id"]
        )
    except HTTPException:
        raise
    except (FileNotFoundError, OSError) as err:
        raise HTTPException(
            status_code=503,
            detail=f"Record embeddings are unavailable ({err}). Recompute the embeddings.",
        ) from err
    except (ValueError, RuntimeError) as err:
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
    return RecordSearchResponse(items=items, total=len(items), model=model, mode=mode, k=body.k, space=space["id"])


async def _refuse_other_weights(provider: InferenceProvider, space: dict[str, Any]) -> None:
    """Refuse a text search the inference would embed with other weights than the space's vectors were.

    A query embedded by other weights ranks the stored vectors by a distance that means nothing, however
    alike the dimensions. Only told checkpoints are compared: a server that tells none, or cannot be
    asked — its embedding call says so then —, embeds the query as the space's model, as before.

    Args:
        provider: The inference the query is to be embedded by.
        space: The space searched.

    Raises:
        HTTPException: 409, the inference serves the model with another checkpoint than the space's.
    """
    if not space["checkpoint"]:
        return
    try:
        served = await provider.list_models(InferenceTask.EMBEDDING)
    except Exception:  # noqa: BLE001 — the embedding call that follows says what is wrong with the server
        return
    checkpoint = next((info.model_path for info in served if info.name == space["model_id"]), None)
    if checkpoint and checkpoint != space["checkpoint"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"The inference serves model '{space['model_id']}' with '{checkpoint}', not the "
                f"'{space['checkpoint']}' these embeddings were computed with: search the embeddings of "
                f"'{checkpoint}', or compute them."
            ),
        )


@router.get(
    "/embedding-spaces",
    response_model=list[EmbeddingSpaceStatus],
    response_model_exclude_none=True,
    operation_id="list_embedding_spaces",
    summary="Embedding spaces",
    description="List the dataset's record embeddings, one space per model and checkpoint, each with its "
    "health, and which one a search naming no model reads.",
)
def list_embedding_spaces(dataset_id: str, dataset: Dataset = Depends(get_dataset_dep)) -> list[EmbeddingSpaceStatus]:
    """Every embeddings space of the dataset, with its health."""
    return [_space_status(dataset, space) for space in dataset.record_embedding_spaces()]


@router.put(
    "/embedding-spaces/default",
    response_model=EmbeddingSpaceStatus,
    response_model_exclude_none=True,
    operation_id="set_default_embedding_space",
    summary="Default embedding space",
    description="Make one of the dataset's embedding spaces the one a search naming no model reads.",
)
def set_default_embedding_space(
    dataset_id: str, body: DefaultEmbeddingSpaceRequest, dataset: Dataset = Depends(get_dataset_dep)
) -> EmbeddingSpaceStatus:
    """Make a space the default one."""
    _held_space(dataset, body.space_id)
    try:
        space = dataset.set_default_record_embedding_space(body.space_id)
    except DatasetAccessError as err:
        raise HTTPException(status_code=409, detail=_unchangeable(err)) from None
    return _space_status(dataset, {**space, "default": True})


@router.delete(
    "/embedding-spaces/{space_id}",
    status_code=204,
    operation_id="delete_embedding_space",
    summary="Delete a model's embeddings",
    description="Delete one model's record embeddings — its space and its table —, the other models' kept. "
    "The default moves to the first space left if it was this one. A computation of that model running "
    "meanwhile writes its next vectors into a space of it again.",
)
def delete_embedding_space(dataset_id: str, space_id: str, dataset: Dataset = Depends(get_dataset_dep)) -> None:
    """Delete one space's embeddings."""
    _held_space(dataset, space_id)
    try:
        dataset.drop_record_embeddings(space_id)
    except DatasetAccessError as err:
        raise HTTPException(status_code=409, detail=_unchangeable(err)) from None


def _unchangeable(error: DatasetAccessError) -> str:
    """Why the dataset's embeddings cannot change, and the one way out the API offers."""
    return f"{error} Compute the embeddings again with force=true: it deletes every model's embeddings first."


def _held_space(dataset: Dataset, space_id: str) -> None:
    """Refuse a space the dataset does not hold, by its id — a name two checkpoints share names none.

    Raises:
        HTTPException: 404, no space of this id.
    """
    if space_id not in {space["id"] for space in dataset.record_embedding_spaces()}:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset.id} has no embedding space '{space_id}'.")


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

    # Another model's vectors go to a space of their own: only the model's own space, broken, asks
    # for force — which empties that space, or every model's when the description cannot be read.
    if not body.force and not dataset.record_embeddings_fully_read():
        raise HTTPException(
            status_code=409,
            detail=(
                "The dataset's embeddings.json cannot be read entirely, so no computation changes it. "
                "Compute with force=true, which deletes every model's embeddings first, or repair the file."
            ),
        )
    # Two checkpoints of one name: the computation, told which the inference serves, checks its own.
    of_name = [space for space in dataset.record_embedding_spaces() if space["model_id"] == body.model]
    health = dataset.record_embedding_health(of_name[0]["id"]) if len(of_name) == 1 else None
    if not body.force and health is not None and health["status"] not in _COMPUTABLE:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Record embeddings of model '{body.model}' are broken ({health['detail']}) "
                "Recompute with force=true."
            ),
        )

    store = JobStore.for_data_dir(_data_dir(settings))
    job_id = submit_embedding_job(store, dataset.path, dataset_id, provider, body.model, force=body.force)
    return ComputeEmbeddingsResponse(job_id=job_id)
