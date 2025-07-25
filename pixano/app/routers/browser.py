# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import NonNegativeInt, PositiveInt

from pixano.app.models import DatasetBrowser, PaginationColumn, PaginationInfo, TableData
from pixano.app.settings import Settings, get_settings
from pixano.datasets.utils.errors import DatasetAccessError
from pixano.features import SchemaGroup, is_image, is_text, is_view_embedding
from pixano.features.utils.image import generate_text_image_base64

from .utils import assert_table_in_group, get_dataset, get_rows


router = APIRouter(prefix="/browser", tags=["Browser"])


@router.get("/{id}", response_model=DatasetBrowser)
async def get_browser(
    request: Request,
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    limit: PositiveInt = 50,
    skip: NonNegativeInt = 0,
    query: str = "",
    embedding_table: str = "",
    where: str | None = None,
    sortcol: str | None = None,
    order: str | None = None,
) -> DatasetBrowser:  # type: ignore
    """Load dataset items for the explorer page.

    Args:
        request: the request object, used to retrieve the current app instance
        id: Dataset ID containing the items.
        settings: App settings.
        limit: Limit number of items.
        skip: Skip number of items.
        query: Text query for semantic search.
        embedding_table: Table name for embeddings.
        where: Where clause.
        sortcol: column to order by
        order: sort order (asc or desc)

    Returns:
        Dataset explorer page.
    """
    # Load dataset
    dataset = get_dataset(id, settings.library_dir, settings.media_dir)

    semantic_search = embedding_table != ""
    if query != "" or embedding_table != "":
        if query == "" or embedding_table == "":
            raise HTTPException(
                status_code=400,
                detail="Both query and model_name should be provided for semantic search.",
            )

    # Get page parameters
    total = dataset.num_rows
    original_limit = limit
    limit = min(limit, total - skip)

    # Get tables
    table_item = SchemaGroup.ITEM.value
    tables_view = sorted(dataset.schema.groups[SchemaGroup.VIEW])

    # get data (items and views)
    if semantic_search:
        try:
            item_rows, distances, list_ids = dataset.semantic_search(query, embedding_table, limit, skip)
        except DatasetAccessError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        if where is not None or sortcol is not None:
            full_item_rows = get_rows(dataset=dataset, table=table_item, where=where, sortcol=sortcol, order=order)
            item_rows = full_item_rows[skip : skip + limit]
            list_ids = [item.id for item in full_item_rows]
        else:
            item_rows = get_rows(dataset=dataset, table=table_item, limit=limit, skip=skip)
            list_ids = dataset.get_all_ids()

    item_ids = [item.id for item in item_rows]
    item_first_media: dict[str, dict] = {}
    for view in tables_view:
        try:
            view_rows = get_rows(dataset=dataset, table=view, item_ids=item_ids)
        except HTTPException:
            view_rows = []
        item_first_media[view] = {}
        for item_id in item_ids:
            # store image or first frame
            item_first_media[view][item_id] = next(filter(lambda v: v.item_ref.id == item_id, view_rows), None)

    # build column headers (PaginationColumn)
    cols = []
    for view in tables_view:
        view_type = "image"
        # NOTE: right now for video we use a frame
        # (first returned by get_rows for each item. May not be the real first frame)
        # when we'll have thumbnail clip, use instead:
        # view_type = "video" if isinstance(item_first_media[view][item_ids[0]], SequenceFrame) else "image"
        cols.append(PaginationColumn(name=view, type=view_type))
    for feat in vars(item_rows[0]).keys():
        cols.append(PaginationColumn(name=feat, type=type(getattr(item_rows[0], feat)).__name__))
    if semantic_search:
        cols.append(PaginationColumn(name="distance", type="float"))

    # build rows
    rows: list[dict[str, Any]] = []
    for i, item in enumerate(item_rows):
        row: dict[str, Any] = {}
        # VIEWS -> thumbnails previews
        for view in tables_view:
            curr_view = item_first_media[view][item.id]
            if curr_view is not None:
                if is_image(type(curr_view)):
                    try:
                        # Try to open image. If image is found, give an url to access via the get_thumbnail endpoint.
                        curr_view.open(settings.media_dir, output_type="image")
                        encoded_url = base64.b64encode(curr_view.url.encode("utf-8")).decode("utf-8")
                        row_view_url = str(request.url_for("get_thumbnail", b64_image_path=encoded_url))
                    except ValueError:
                        # If image not accesible, set view_url to empty string.
                        row_view_url = ""
                elif is_text(type(curr_view)):
                    row_view_url = generate_text_image_base64(curr_view.content[:80])
                row[view] = row_view_url

        # ITEM features
        for feat in vars(item).keys():
            row[feat] = getattr(item, feat)
        # DISTANCE
        if semantic_search:
            row["distance"] = distances[i]

        rows.append(row)

    semantic_search_list = sorted(
        [
            table_name
            for table_name in dataset.schema.groups[SchemaGroup.EMBEDDING]
            if is_view_embedding(dataset.schema.schemas[table_name])
        ]
    )
    # Return dataset items
    return DatasetBrowser(
        id=id,
        name=dataset.info.name,
        table_data=TableData(columns=cols, rows=rows),
        pagination=PaginationInfo(current_page=skip, page_size=original_limit, total_size=total),
        semantic_search=semantic_search_list,
        item_ids=list_ids,
    )


@router.get("/item_ids/{id}", response_model=list[str])
async def get_items_ids(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[str]:
    """Get all item ids.

    Args:
        id: Dataset ID.
        settings: App settings.

    Returns:
        List of dataset items ids.
    """
    dataset = get_dataset(id, settings.library_dir, None)
    assert_table_in_group(dataset, SchemaGroup.ITEM.value, SchemaGroup.ITEM)
    return dataset.get_all_ids()
