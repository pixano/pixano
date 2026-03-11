"""Subtype-specific view routers."""

import io
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from lancedb.pydantic import LanceModel

from pixano.api.media import MULTIPART_BOUNDARY, iter_multipart_frames, media_type_from_format
from pixano.api.models import ImageResponse, PaginatedResponse, SFrameResponse, TextResponse
from pixano.api.routers._deps import PaginationParams, get_dataset_dep
from pixano.datasets import Dataset
from pixano.datasets.utils import DatasetPaginationError
from pixano.datasets.utils.errors import DatasetAccessError


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Views"])

T = TypeVar("T", bound=LanceModel)
R = TypeVar("R")

IMAGE_TABLE = "images"
TEXT_TABLE = "texts"
SFRAME_TABLE = "sequence_frames"


def _combine_where(*clauses: str | None) -> str | None:
    filtered = [clause for clause in clauses if clause]
    return " AND ".join(filtered) if filtered else None


def _count_rows(dataset: Dataset, table_name: str, where: str | None) -> int:
    table = dataset.open_table(table_name)
    return table.count_rows(where) if where else table.count_rows()


def _list_rows(
    dataset: Dataset,
    table_name: str,
    *,
    pagination: PaginationParams,
    record_id: str | None = None,
    view_name: str | None = None,
    where: str | None = None,
) -> tuple[list[T], int]:
    combined_where = _combine_where(
        f"record_id = '{record_id}'" if record_id else None,
        f"logical_name = '{view_name}'" if view_name else None,
        f"({where})" if where else None,
    )

    try:
        total = _count_rows(dataset, table_name, combined_where)
        rows = dataset.get_data(
            table_name=table_name,
            where=combined_where,
            limit=pagination.limit,
            skip=pagination.offset,
        )
    except DatasetPaginationError as err:
        raise HTTPException(status_code=400, detail=f"Invalid query parameters. {err}") from err
    except DatasetAccessError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    return (rows or []), total


def _get_row(dataset: Dataset, table_name: str, row_id: str) -> T:
    try:
        row = dataset.get_data(table_name, ids=row_id)
    except DatasetAccessError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    if row is None:
        raise HTTPException(status_code=404, detail=f"Resource '{row_id}' not found.")
    return row


def _stream_blob(dataset: Dataset, table_name: str, row_id: str) -> StreamingResponse:
    try:
        result = dataset.get_view_binary(table_name, row_id)
    except DatasetAccessError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    if result is None:
        raise HTTPException(status_code=404, detail=f"Resource '{row_id}' has no embedded blob.")

    blob_data, fmt = result
    return StreamingResponse(
        io.BytesIO(blob_data),
        media_type=media_type_from_format(fmt),
        headers={"Content-Length": str(len(blob_data))},
    )


def _image_src(dataset_id: str, resource_name: str, row: Any) -> str:
    uri = getattr(row, "uri", "") or ""
    if uri:
        return uri
    return f"/datasets/{dataset_id}/{resource_name}/{row.id}/blob"


def _to_image_response(dataset_id: str, row: Any) -> ImageResponse:
    return ImageResponse(
        id=row.id,
        record_id=row.record_id,
        logical_name=getattr(row, "logical_name", "") or "",
        created_at=str(getattr(row, "created_at", "") or ""),
        updated_at=str(getattr(row, "updated_at", "") or ""),
        width=getattr(row, "width", 0) or 0,
        height=getattr(row, "height", 0) or 0,
        format=getattr(row, "format", "") or "",
        src=_image_src(dataset_id, "images", row),
    )


def _to_text_response(row: Any) -> TextResponse:
    return TextResponse(
        id=row.id,
        record_id=row.record_id,
        logical_name=getattr(row, "logical_name", "") or "",
        created_at=str(getattr(row, "created_at", "") or ""),
        updated_at=str(getattr(row, "updated_at", "") or ""),
        content=getattr(row, "content", "") or "",
        uri=getattr(row, "uri", "") or "",
    )


def _to_sframe_response(dataset_id: str, row: Any) -> SFrameResponse:
    return SFrameResponse(
        id=row.id,
        record_id=row.record_id,
        logical_name=getattr(row, "logical_name", "") or "",
        created_at=str(getattr(row, "created_at", "") or ""),
        updated_at=str(getattr(row, "updated_at", "") or ""),
        width=getattr(row, "width", 0) or 0,
        height=getattr(row, "height", 0) or 0,
        format=getattr(row, "format", "") or "",
        timestamp=float(getattr(row, "timestamp", 0) or 0),
        frame_index=int(getattr(row, "frame_index", 0) or 0),
        src=_image_src(dataset_id, "sframes", row),
    )


def _list_image_responses(
    dataset_id: str,
    dataset: Dataset,
    pagination: PaginationParams,
    *,
    record_id: str | None = None,
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[ImageResponse]:
    rows, total = _list_rows(
        dataset,
        IMAGE_TABLE,
        pagination=pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )
    return PaginatedResponse(
        items=[_to_image_response(dataset_id, row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def _list_text_responses(
    dataset: Dataset,
    pagination: PaginationParams,
    *,
    record_id: str | None = None,
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[TextResponse]:
    rows, total = _list_rows(
        dataset,
        TEXT_TABLE,
        pagination=pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )
    return PaginatedResponse(
        items=[_to_text_response(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def _list_sframe_responses(
    dataset_id: str,
    dataset: Dataset,
    pagination: PaginationParams,
    *,
    record_id: str | None = None,
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[SFrameResponse]:
    rows, total = _list_rows(
        dataset,
        SFRAME_TABLE,
        pagination=pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )
    return PaginatedResponse(
        items=[_to_sframe_response(dataset_id, row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/images", response_model=PaginatedResponse[ImageResponse], operation_id="list_images")
def list_images(
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    record_id: str | None = None,
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[ImageResponse]:
    return _list_image_responses(
        dataset_id,
        dataset,
        pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )


@router.get("/images/{id}", response_model=ImageResponse, operation_id="get_image")
def get_image(id: str, dataset_id: str, dataset: Dataset = Depends(get_dataset_dep)) -> ImageResponse:
    return _to_image_response(dataset_id, _get_row(dataset, IMAGE_TABLE, id))


@router.get("/images/{id}/blob", operation_id="get_image_blob")
def get_image_blob(id: str, dataset: Dataset = Depends(get_dataset_dep)) -> StreamingResponse:
    return _stream_blob(dataset, IMAGE_TABLE, id)


@router.get("/texts", response_model=PaginatedResponse[TextResponse], operation_id="list_texts")
def list_texts(
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    record_id: str | None = None,
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[TextResponse]:
    return _list_text_responses(
        dataset,
        pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )


@router.get("/texts/{id}", response_model=TextResponse, operation_id="get_text")
def get_text(id: str, dataset: Dataset = Depends(get_dataset_dep)) -> TextResponse:
    return _to_text_response(_get_row(dataset, TEXT_TABLE, id))


@router.get("/sframes", response_model=PaginatedResponse[SFrameResponse], operation_id="list_sframes")
def list_sframes(
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    record_id: str | None = None,
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[SFrameResponse]:
    return _list_sframe_responses(
        dataset_id,
        dataset,
        pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )


@router.get("/sframes/{id}", response_model=SFrameResponse, operation_id="get_sframe")
def get_sframe(id: str, dataset_id: str, dataset: Dataset = Depends(get_dataset_dep)) -> SFrameResponse:
    return _to_sframe_response(dataset_id, _get_row(dataset, SFRAME_TABLE, id))


@router.get("/sframes/{id}/blob", operation_id="get_sframe_blob")
def get_sframe_blob(id: str, dataset: Dataset = Depends(get_dataset_dep)) -> StreamingResponse:
    return _stream_blob(dataset, SFRAME_TABLE, id)


@router.get(
    "/records/{record_id}/images",
    response_model=PaginatedResponse[ImageResponse],
    operation_id="list_record_images",
)
def list_record_images(
    record_id: str,
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[ImageResponse]:
    return _list_image_responses(
        dataset_id,
        dataset,
        pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )


@router.get(
    "/records/{record_id}/texts",
    response_model=PaginatedResponse[TextResponse],
    operation_id="list_record_texts",
)
def list_record_texts(
    record_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[TextResponse]:
    return _list_text_responses(
        dataset,
        pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )


@router.get(
    "/records/{record_id}/sframes",
    response_model=PaginatedResponse[SFrameResponse],
    operation_id="list_record_sframes",
)
def list_record_sframes(
    record_id: str,
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    pagination: PaginationParams = Depends(),
    view_name: str | None = None,
    where: str | None = None,
) -> PaginatedResponse[SFrameResponse]:
    return _list_sframe_responses(
        dataset_id,
        dataset,
        pagination,
        record_id=record_id,
        view_name=view_name,
        where=where,
    )


@router.get(
    "/records/{record_id}/sframes/batch",
    operation_id="get_record_sframe_batch",
    responses={
        200: {
            "description": "Batch of temporal frames as a multipart binary stream.",
            "content": {"multipart/x-mixed-replace": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def get_record_sframe_batch(
    record_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    view_name: str | None = None,
    start_frame: Annotated[int, Query(ge=0)] = 0,
    batch_size: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> StreamingResponse:
    try:
        frames = dataset.get_temporal_view_batch(
            SFRAME_TABLE,
            record_id=record_id,
            view_name=view_name,
            start_frame=start_frame,
            batch_size=batch_size,
        )
    except DatasetAccessError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    if not frames:
        raise HTTPException(status_code=404, detail="No frames found for the given parameters.")

    payloads = [(frame_index, data, media_type_from_format(fmt)) for frame_index, data, fmt in frames]
    return StreamingResponse(
        iter_multipart_frames(payloads),
        media_type=f"multipart/x-mixed-replace; boundary={MULTIPART_BOUNDARY.decode()}",
        headers={
            "X-Total-Frames": str(len(frames)),
            "X-Start-Frame": str(start_frame),
            "X-Batch-Size": str(batch_size),
        },
    )
