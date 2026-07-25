# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Records router with optional explorer preview expansion."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from pixano.api.models import PaginatedResponse, PreviewDescriptor, RecordListResponse, RecordResponse
from pixano.api.query import FilterCompileError, build_column_catalogue, compile_filters, validate_sort
from pixano.api.resources import RECORD_RESOURCE
from pixano.api.routers._deps import PaginationParams, RecordQueryParams, get_dataset_dep
from pixano.api.service import BaseService
from pixano.datasets import Dataset, TableQueryBuilder
from pixano.datasets.utils import DatasetAccessError
from pixano.utils.python import to_sql_list


router = APIRouter(prefix="/datasets/{dataset_id}/records", tags=["Records"])

_ALLOWED_INCLUDES = frozenset({"view_previews"})


def _parse_include(include: str | None) -> set[str]:
    if include is None:
        return set()

    values = {value.strip() for value in include.split(",") if value.strip()}
    unknown_values = sorted(values - _ALLOWED_INCLUDES)
    if unknown_values:
        allowed = ", ".join(sorted(_ALLOWED_INCLUDES))
        unknown = ", ".join(unknown_values)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown include value(s): {unknown}. Allowed values: {allowed}.",
        )
    return values


def _query_preview_rows(
    dataset: Dataset,
    table_name: str,
    columns: list[str],
    record_ids: list[str],
    *,
    extra_where: str | None = None,
) -> list[dict[str, Any]]:
    if not record_ids or table_name not in dataset.info.tables:
        return []

    where = f"record_id IN {to_sql_list(record_ids)}"
    if extra_where is not None:
        where += f" AND {extra_where}"
    try:
        return (
            TableQueryBuilder(dataset.open_table(table_name), dataset._db_connection)  # noqa: SLF001
            .select(columns)
            .where(where)
            .to_list()
        )
    except DatasetAccessError as err:
        raise HTTPException(status_code=500, detail=f"Internal server error. {err}") from err


def _preview_url(dataset_id: str, resource: str, row_id: str, uri: object) -> str:
    """Datalake rows (spec §6 uri mode) are browser-loadable directly; embedded rows go through /preview."""
    if isinstance(uri, str) and uri.startswith(("http://", "https://")):
        return uri
    return f"/datasets/{dataset_id}/{resource}/{row_id}/preview"


def _resolve_view_previews(
    dataset_id: str, dataset: Dataset, record_ids: list[str]
) -> dict[str, dict[str, PreviewDescriptor]]:
    previews_by_record: dict[str, dict[str, PreviewDescriptor]] = {record_id: {} for record_id in record_ids}

    # Image-family views live in either the `images` table (plain Image) or the
    # `calibrated_images` table (CalibratedImage, e.g. nuScenes cameras). Both are
    # served through the `/images/{id}/preview` route (see views._resolve_image_table),
    # so we emit the same descriptor for either. `calibrated_images` is queried first
    # so it wins on the rare dataset that carries both, matching _resolve_image_table.
    for table_name in ("calibrated_images", "images"):
        for row in _query_preview_rows(dataset, table_name, ["id", "record_id", "logical_name", "uri"], record_ids):
            record_id = str(row.get("record_id", "") or "")
            logical_name = str(row.get("logical_name", "") or "")
            row_id = str(row.get("id", "") or "")
            if not record_id or not logical_name or not row_id:
                continue
            logical_previews = previews_by_record.setdefault(record_id, {})
            if logical_name in logical_previews:
                continue
            logical_previews[logical_name] = PreviewDescriptor(
                resource="images",
                id=row_id,
                kind="image",
                preview_url=_preview_url(dataset_id, "images", row_id, row.get("uri")),
            )

    # Only the first frame of each sequence is needed for a thumbnail. Filter to
    # frame 0 (BTREE-indexed → native path) instead of ordering the whole
    # sequence_frames table by frame_index with no limit, which would materialize
    # every frame of every video just to render a page of previews.
    sframe_rows = _query_preview_rows(
        dataset,
        "sequence_frames",
        ["id", "record_id", "logical_name", "frame_index", "uri"],
        record_ids,
        extra_where="frame_index = 0",
    )
    for row in sframe_rows:
        record_id = str(row.get("record_id", "") or "")
        logical_name = str(row.get("logical_name", "") or "")
        row_id = str(row.get("id", "") or "")
        if not record_id or not logical_name or not row_id:
            continue
        logical_previews = previews_by_record.setdefault(record_id, {})
        if logical_name in logical_previews:
            continue
        logical_previews[logical_name] = PreviewDescriptor(
            resource="sframes",
            id=row_id,
            kind="image",
            preview_url=_preview_url(dataset_id, "sframes", row_id, row.get("uri")),
        )

    # Point clouds render a bird's-eye-view PNG at ingestion, served through
    # `/point-clouds/{id}/preview`. `kind="image"` so the same UI preview path
    # (an <img> tag) displays it — it is a raster after all.
    for row in _query_preview_rows(dataset, "point_clouds", ["id", "record_id", "logical_name"], record_ids):
        record_id = str(row.get("record_id", "") or "")
        logical_name = str(row.get("logical_name", "") or "")
        row_id = str(row.get("id", "") or "")
        if not record_id or not logical_name or not row_id:
            continue
        logical_previews = previews_by_record.setdefault(record_id, {})
        if logical_name in logical_previews:
            continue
        logical_previews[logical_name] = PreviewDescriptor(
            resource="point-clouds",
            id=row_id,
            kind="image",
            preview_url=f"/datasets/{dataset_id}/point-clouds/{row_id}/preview",
        )

    return previews_by_record


@router.get(
    "",
    response_model=PaginatedResponse[RecordListResponse],
    response_model_exclude_none=True,
    operation_id="list_records",
    summary="List records",
    description="List records in a dataset with typed filters, free-text search, sorting, "
    "pagination, and explorer expansions.",
)
def list_records(
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    query: RecordQueryParams = Depends(),
) -> PaginatedResponse[RecordListResponse]:
    """List records with typed filters, free-text search, sorting, and view previews."""
    includes = _parse_include(query.include)

    catalogue = build_column_catalogue(dataset, "records")
    try:
        where, _referenced, index_servable = compile_filters(catalogue, query.filter, query.q)
        sortcol, order = validate_sort(catalogue, query.sort, query.order)
    except FilterCompileError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None

    # Fold in a deprecated raw `where` clause (back-compat) if present.
    raw_where = bool(query.where)
    if raw_where:
        where = f"({query.where})" if where is None else f"{where} AND ({query.where})"

    service = BaseService(dataset, RECORD_RESOURCE)
    records_page = service.list(
        where=where,
        limit=pagination.limit,
        offset=pagination.offset,
        sortcol=sortcol,
        order=order,
        force_full_scan=not index_servable,
        raw_where=raw_where,
    )

    record_ids = [record.id for record in records_page.items]
    previews_by_record = (
        _resolve_view_previews(dataset_id, dataset, record_ids) if "view_previews" in includes and record_ids else {}
    )

    items = [
        RecordListResponse.model_validate(
            {
                **record.model_dump(),
                "view_previews": previews_by_record.get(record.id) or None,
            }
        )
        for record in records_page.items
    ]
    return PaginatedResponse(
        items=items, total=records_page.total, limit=records_page.limit, offset=records_page.offset
    )


@router.get(
    "/{id}",
    response_model=RecordResponse,
    operation_id="get_record",
    summary="Get a record",
    description="Fetch a single record by id.",
)
def get_record(id: str, dataset: Dataset = Depends(get_dataset_dep)) -> RecordResponse:  # type: ignore[valid-type]
    """Fetch a single record by ID."""
    service = BaseService(dataset, RECORD_RESOURCE)
    return service.get(id)


@router.post(
    "",
    response_model=RecordResponse,
    status_code=201,
    operation_id="create_record",
    summary="Create a record",
    description="Create a new record row in the dataset.",
)
def create_record(body: RECORD_RESOURCE.create_model, dataset: Dataset = Depends(get_dataset_dep)) -> Any:  # type: ignore[name-defined]
    """Create a new record row in the dataset."""
    service = BaseService(dataset, RECORD_RESOURCE)
    return service.create(body.model_dump())


@router.put(
    "/{id}",
    response_model=RecordResponse,
    operation_id="replace_record",
    summary="Update a record",
    description="Replace mutable fields on an existing record.",
)
def update_record(
    id: str,
    body: RECORD_RESOURCE.update_model,  # type: ignore[name-defined]
    dataset: Dataset = Depends(get_dataset_dep),
) -> Any:
    """Replace mutable fields on an existing record."""
    service = BaseService(dataset, RECORD_RESOURCE)
    return service.update(id, body.model_dump(exclude_unset=True))


@router.delete(
    "/{id}",
    status_code=204,
    operation_id="delete_record",
    summary="Delete a record",
    description="Delete a single record by id.",
)
def delete_record(id: str, dataset: Dataset = Depends(get_dataset_dep)) -> None:
    """Delete a single record by ID."""
    service = BaseService(dataset, RECORD_RESOURCE)
    service.delete(id)
