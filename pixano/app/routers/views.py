# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import io
from collections.abc import Generator
from typing import Annotated

import pyarrow as pa
import pyarrow.compute as pc
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from starlette.responses import Response

from pixano.app.models.views import ViewModel
from pixano.app.settings import Settings, get_settings
from pixano.datasets.queries import TableQueryBuilder
from pixano.features.schemas.schema_group import SchemaGroup

from .utils import (
    create_row_handler,
    create_rows_handler,
    delete_row_handler,
    delete_rows_handler,
    get_dataset,
    get_row_handler,
    get_rows_handler,
    update_row_handler,
    update_rows_handler,
)


router = APIRouter(prefix="/views", tags=["Views"])

# MIME type mapping for common media formats
_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "PNG": "image/png",
    "png": "image/png",
    "WEBP": "image/webp",
    "webp": "image/webp",
    "TIFF": "image/tiff",
    "tiff": "image/tiff",
    "BMP": "image/bmp",
    "bmp": "image/bmp",
    "GIF": "image/gif",
    "gif": "image/gif",
    "pdf": "application/pdf",
    "PDF": "application/pdf",
    "ply": "application/x-ply",
    "pcd": "application/x-pcd",
}

_BOUNDARY = b"frame_boundary"


def _generate_multipart_frames(
    arrow_table: pa.Table,
    blob_col_name: str,
    format_col: str,
) -> Generator[bytes, None, None]:
    """Yield multipart/x-mixed-replace parts from an Arrow table of frames.

    Each part contains the frame blob with appropriate headers.

    Args:
        arrow_table: Sorted Arrow table with frame data.
        blob_col_name: Column name containing the blob data.
        format_col: Column name containing the format string.
    """
    has_format = format_col in arrow_table.column_names
    frame_index_col = arrow_table.column("frame_index")
    blob_col = arrow_table.column(blob_col_name)

    for i in range(arrow_table.num_rows):
        blob = blob_col[i].as_py()
        if not blob:
            continue
        fmt = arrow_table.column(format_col)[i].as_py() if has_format else "bin"
        mime = _FORMAT_TO_MIME.get(fmt, "application/octet-stream")
        idx = frame_index_col[i].as_py()

        header = (
            b"--" + _BOUNDARY + b"\r\n"
            b"Content-Type: " + mime.encode() + b"\r\n"
            b"Content-Length: " + str(len(blob)).encode() + b"\r\n"
            b"X-Frame-Index: " + str(idx).encode() + b"\r\n"
            b"\r\n"
        )
        yield header
        yield blob
        yield b"\r\n"

    yield b"--" + _BOUNDARY + b"--\r\n"


@router.get(
    "/{dataset_id}/{view_name}/{row_id}/blob",
    operation_id="get_view_blob",
    responses={
        200: {
            "description": "Raw blob bytes for the requested view.",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def get_view_blob(
    dataset_id: str,
    view_name: str,
    row_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Stream the raw blob of a specific view at a specific row.

    Args:
        dataset_id: Dataset ID.
        view_name: View name (column prefix in media-type table).
        row_id: Row ID in the media-type table.
        settings: App settings.

    Returns:
        StreamingResponse with the raw blob bytes.
    """
    dataset = get_dataset(dataset_id, settings.library_dir, settings.media_dir)

    # Resolve view_name -> media_table via schema.view_columns
    if view_name not in dataset.schema.view_columns:
        raise HTTPException(status_code=404, detail=f"View '{view_name}' not found in dataset schema.")

    vc = dataset.schema.view_columns[view_name]
    table = dataset.open_table(vc.media_table)

    # Fetch only the blob column and format for this view
    select_cols = ["id", "blob"]
    format_col = "format"
    if format_col in [f.name for f in table.schema]:
        select_cols.append(format_col)

    rows = (
        TableQueryBuilder(table, dataset._db_connection)
        .select(select_cols)
        .where(f"id = '{row_id}' AND view_name = '{view_name}'")
        .to_list()
    )

    if not rows:
        raise HTTPException(status_code=404, detail=f"Row '{row_id}' not found in table '{vc.media_table}'.")

    blob = rows[0].get("blob", b"")
    if not blob:
        raise HTTPException(status_code=404, detail="No blob data found for this view.")

    fmt = rows[0].get(format_col, "bin")
    mime_type = _FORMAT_TO_MIME.get(fmt, "application/octet-stream")

    return StreamingResponse(
        io.BytesIO(blob),
        media_type=mime_type,
        headers={"Content-Length": str(len(blob))},
    )


@router.get(
    "/{dataset_id}/{view_name}/batch",
    operation_id="get_view_blob_batch",
    responses={
        200: {
            "description": "Batch of video/sequence frames as multipart stream.",
            "content": {"multipart/x-mixed-replace": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def get_view_blob_batch(
    dataset_id: str,
    view_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
    item_id: str = Query(..., description="Item ID for the video/sequence"),
    start_frame: int = Query(0, ge=0),
    batch_size: int = Query(100, ge=1, le=1000),
) -> StreamingResponse:
    """Stream a batch of video/sequence frames as multipart/x-mixed-replace.

    Returns multiple frames in a single response, reducing HTTP round-trips
    for temporal views (e.g., SequenceFrame).

    Args:
        dataset_id: Dataset ID.
        view_name: View name (column prefix in media-type table).
        settings: App settings.
        item_id: Item ID to fetch frames for.
        start_frame: Starting frame index (inclusive).
        batch_size: Number of frames to return (max 1000).

    Returns:
        StreamingResponse with multipart/x-mixed-replace body.
    """
    dataset = get_dataset(dataset_id, settings.library_dir, settings.media_dir)

    # Resolve view_name -> media table
    if view_name not in dataset.schema.view_columns:
        raise HTTPException(status_code=404, detail=f"View '{view_name}' not found in dataset schema.")

    vc = dataset.schema.view_columns[view_name]
    table = dataset.open_table(vc.media_table)

    # Validate that this is a temporal view (has frame_index column)
    table_column_names = [f.name for f in table.schema]
    if "frame_index" not in table_column_names:
        raise HTTPException(status_code=400, detail=f"View '{view_name}' is not a temporal view (no frame_index).")

    # Sanitize item_id to prevent injection
    if "'" in item_id:
        raise HTTPException(status_code=400, detail="Invalid item_id.")

    # Build query
    end_frame = start_frame + batch_size
    where_clause = (
        f"item_id = '{item_id}' "
        f"AND view_name = '{view_name}' "
        f"AND frame_index >= {start_frame} "
        f"AND frame_index < {end_frame}"
    )

    select_cols = ["id", "blob", "frame_index"]
    format_col = "format"
    if format_col in table_column_names:
        select_cols.append(format_col)

    arrow_table = (
        TableQueryBuilder(table, dataset._db_connection)
        .select(select_cols)
        .where(where_clause)
        .limit(batch_size)
        .to_arrow()
    )

    if arrow_table.num_rows == 0:
        raise HTTPException(status_code=404, detail="No frames found for the given parameters.")

    # Sort by frame_index
    sorted_indices = pc.sort_indices(arrow_table, sort_keys=[("frame_index", "ascending")])
    arrow_table = arrow_table.take(sorted_indices)

    return StreamingResponse(
        _generate_multipart_frames(arrow_table, "blob", format_col),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY.decode()}",
        headers={
            "X-Total-Frames": str(arrow_table.num_rows),
            "X-Start-Frame": str(start_frame),
            "X-Batch-Size": str(batch_size),
        },
    )


@router.get("/{dataset_id}/{table}", response_model=list[ViewModel], operation_id="list_views")
def get_views(
    dataset_id: str,
    table: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
    where: str | None = None,
    item_ids: list[str] | None = Query(None),
) -> list[ViewModel]:
    """Get views from a table of a dataset.

    They can be filtered by IDs, item IDs, a where clause or paginated.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        settings: App settings.
        ids: IDs of the views.
        limit: Limit number of views.
        skip: Skip number of views.
        where: Where clause.
        item_ids: Item IDs.

    Returns:
        List of views.
    """
    return get_rows_handler(
        dataset_id=dataset_id,
        group=SchemaGroup.VIEW,
        table=table,
        settings=settings,
        where=where,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
    )


@router.get("/{dataset_id}/{table}/{id}", response_model=ViewModel, operation_id="get_view")
def get_view(dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> ViewModel:
    """Get a view from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the view.
        settings: App settings.

    Returns:
        The view.
    """
    return get_row_handler(dataset_id, SchemaGroup.VIEW, table, id, settings)


@router.post("/{dataset_id}/{table}", response_model=list[ViewModel], status_code=201, operation_id="create_views")
def create_views(
    dataset_id: str,
    table: str,
    views: list[ViewModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ViewModel]:
    """Add views in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        views: Views to add.
        settings: App settings.

    Returns:
        List of views added.
    """
    return create_rows_handler(dataset_id, SchemaGroup.VIEW, table, views, settings)


@router.post("/{dataset_id}/{table}/{id}", response_model=ViewModel, status_code=201, operation_id="create_view")
def create_view(
    dataset_id: str,
    table: str,
    id: str,
    view: ViewModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ViewModel:
    """Add a view in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the view.
        view: View to add.
        settings: App settings.

    Returns:
        The view added.
    """
    return create_row_handler(dataset_id, SchemaGroup.VIEW, table, id, view, settings)


@router.put("/{dataset_id}/{table}/{id}", response_model=ViewModel, operation_id="update_view")
def update_view(
    dataset_id: str,
    table: str,
    id: str,
    view: ViewModel,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ViewModel:
    """Update a view in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the view.
        view: View to update.
        settings: App settings.

    Returns:
        The view updated.
    """
    return update_row_handler(dataset_id, SchemaGroup.VIEW, table, id, view, settings)


@router.put("/{dataset_id}/{table}", response_model=list[ViewModel], operation_id="update_views")
def update_views(
    dataset_id: str,
    table: str,
    views: list[ViewModel],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ViewModel]:
    """Update views in a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        views: Views to update.
        settings: App settings.

    Returns:
        List of views updated.
    """
    return update_rows_handler(dataset_id, SchemaGroup.VIEW, table, views, settings)


@router.delete("/{dataset_id}/{table}/{id}", status_code=204, response_class=Response, operation_id="delete_view")
def delete_view(dataset_id: str, table: str, id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Delete a view from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        id: ID of the view to delete.
        settings: App settings.
    """
    delete_row_handler(dataset_id, SchemaGroup.VIEW, table, id, settings)


@router.delete("/{dataset_id}/{table}", status_code=204, response_class=Response, operation_id="delete_views")
def delete_views(
    dataset_id: str,
    table: str,
    ids: Annotated[list[str], Query()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Delete views from a table of a dataset.

    Args:
        dataset_id: Dataset ID containing the table.
        table: Table name.
        ids: IDs of the views to delete.
        settings: App settings.
    """
    delete_rows_handler(dataset_id, SchemaGroup.VIEW, table, ids, settings)
