"""Records router with optional explorer preview expansion."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.api.models import PaginatedResponse, PreviewDescriptor, RecordListResponse, RecordResponse
from pixano.api.resources import RECORD_RESOURCE
from pixano.api.routers._deps import FilterParams, PaginationParams, get_dataset_dep
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
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    if not record_ids or table_name not in dataset.info.tables:
        return []

    try:
        query = (
            TableQueryBuilder(dataset.open_table(table_name), dataset._db_connection)
            .select(columns)
            .where(  # noqa: SLF001
                f"record_id IN {to_sql_list(record_ids)}"
            )
        )
        if order_by is not None:
            query = query.order_by(order_by)
        return query.to_list()
    except DatasetAccessError as err:
        raise HTTPException(status_code=500, detail=f"Internal server error. {err}") from err


def _resolve_view_previews(
    dataset_id: str, dataset: Dataset, record_ids: list[str]
) -> dict[str, dict[str, PreviewDescriptor]]:
    previews_by_record: dict[str, dict[str, PreviewDescriptor]] = {record_id: {} for record_id in record_ids}

    image_rows = _query_preview_rows(dataset, "images", ["id", "record_id", "logical_name"], record_ids)
    for row in image_rows:
        record_id = str(row.get("record_id", "") or "")
        logical_name = str(row.get("logical_name", "") or "")
        row_id = str(row.get("id", "") or "")
        if not record_id or not logical_name or not row_id:
            continue
        previews_by_record.setdefault(record_id, {})[logical_name] = PreviewDescriptor(
            resource="images",
            id=row_id,
            kind="image",
            preview_url=f"/datasets/{dataset_id}/images/{row_id}/preview",
        )

    sframe_rows = _query_preview_rows(
        dataset,
        "sequence_frames",
        ["id", "record_id", "logical_name", "frame_index"],
        record_ids,
        order_by="frame_index",
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
            preview_url=f"/datasets/{dataset_id}/sframes/{row_id}/preview",
        )

    return previews_by_record


def _list_record_kwargs(filters: FilterParams, pagination: PaginationParams) -> dict[str, Any]:
    return {
        "where": filters.where,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get(
    "",
    response_model=PaginatedResponse[RecordListResponse],
    response_model_exclude_none=True,
    operation_id="list_records",
    summary="List records",
    description="List records in a dataset with optional filters, pagination, and explorer expansions.",
)
def list_records(
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    include: str | None = Query(default=None),
) -> PaginatedResponse[RecordListResponse]:
    includes = _parse_include(include)
    service = BaseService(dataset, RECORD_RESOURCE)
    records_page = service.list(**_list_record_kwargs(filters, pagination))

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
def get_record(id: str, dataset: Dataset = Depends(get_dataset_dep)) -> RecordResponse:
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
def create_record(body: RECORD_RESOURCE.create_model, dataset: Dataset = Depends(get_dataset_dep)) -> RecordResponse:
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
    id: str, body: RECORD_RESOURCE.update_model, dataset: Dataset = Depends(get_dataset_dep)
) -> RecordResponse:
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
    service = BaseService(dataset, RECORD_RESOURCE)
    service.delete(id)
