# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import NonNegativeInt, PositiveInt

from pixano.app.models import DatasetBrowser, PaginationColumn, PaginationInfo, TableData
from pixano.app.settings import Settings, get_settings
from pixano.datasets.utils.errors import DatasetAccessError
from pixano.features import SchemaGroup, is_image, is_text, is_view_embedding
from pixano.features.utils.image import generate_text_image_base64
from pathlib import Path

from .utils import assert_table_in_group, get_dataset, get_rows


router = APIRouter(prefix="/browser", tags=["Browser"])

# Lazily-populated per-path cache: keyed by media_dir, maps relative_url → exists bool
_media_file_cache: dict[str, dict[str, bool]] = {}


def _media_file_exists(media_dir: Path, relative_url: str) -> bool:
    """Check if a media file exists, using a lazily-populated per-path cache."""
    cache_key = str(media_dir)
    if cache_key not in _media_file_cache:
        _media_file_cache[cache_key] = {}
    path_cache = _media_file_cache[cache_key]
    if relative_url not in path_cache:
        path_cache[relative_url] = (media_dir / relative_url).is_file()
    return path_cache[relative_url]


@router.get("/{id}", response_model=DatasetBrowser)
def get_browser(
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

    # Compute total size: use count_rows_where for filtered queries, num_rows for unfiltered
    if where is not None:
        total = dataset.count_rows_where(where=where)
    else:
        total = dataset.num_rows

    original_limit = limit
    limit = min(limit, total - skip)

    # Get tables
    table_item = SchemaGroup.ITEM.value
    tables_view = sorted(dataset.schema.groups[SchemaGroup.VIEW])

    # get data (items and views)
    if semantic_search:
        try:
            item_rows, distances, _ = dataset.semantic_search(query, embedding_table, limit, skip)
        except DatasetAccessError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        if where is not None or sortcol is not None:
            item_rows = get_rows(
                dataset=dataset, table=table_item, where=where, sortcol=sortcol, order=order, limit=limit, skip=skip
            )
        else:
            item_rows = get_rows(dataset=dataset, table=table_item, limit=limit, skip=skip)

    item_ids = [item.id for item in item_rows]

    # Fetch view data in parallel (each view is a separate LanceDB table)
    def _fetch_view(view_name):
        try:
            return view_name, get_rows(dataset=dataset, table=view_name, item_ids=item_ids)
        except Exception:
            return view_name, []

    item_first_media: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(tables_view) or 1) as executor:
        view_results = list(executor.map(_fetch_view, tables_view))

    # Build item_id → first media mapping per view
    item_id_set = set(item_ids)
    for view, view_rows in view_results:
        view_by_item: dict[str, Any] = {}
        for row in view_rows:
            rid = row.item_ref.id
            if rid in item_id_set and rid not in view_by_item:
                view_by_item[rid] = row
        item_first_media[view] = {item_id: view_by_item.get(item_id) for item_id in item_ids}

    # build column headers (PaginationColumn)
    cols = []
    for view in tables_view:
        view_type = "image"
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
                    # Check media file cache instead of disk I/O
                    if _media_file_exists(settings.media_dir, curr_view.url):
                        encoded_url = base64.b64encode(curr_view.url.encode("utf-8")).decode("utf-8")
                        row_view_url = str(request.url_for("get_thumbnail", b64_image_path=encoded_url))
                    else:
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
    )


@router.get("/item_ids/{id}", response_model=list[str])
def get_items_ids(
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
