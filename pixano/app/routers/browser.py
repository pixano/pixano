# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

import polars as pl
from fastapi import APIRouter, Depends, HTTPException

from pixano.app.models import DatasetBrowser, PaginationColumn, PaginationInfo, TableData
from pixano.app.settings import Settings, get_settings
from pixano.features import SchemaGroup, is_view_embedding

from .utils import get_dataset, get_rows


router = APIRouter(prefix="/browser", tags=["Browser"])


@router.get("/{id}", response_model=DatasetBrowser)
async def get_browser(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 50,
    skip: int = 0,
    query: str = "",
    table: str = "",
) -> DatasetBrowser:  # type: ignore
    """Load dataset items for Explorer page.

    Args:
        id: Dataset ID.
        settings: App settings.
        limit: Limit number of items.
        skip: Skip number of items.
        query: Text query for semantic search.
        table: Table name for embeddings.

    Returns:
        Dataset explorer page.
    """
    # Load dataset
    dataset = get_dataset(id, settings.library_dir, settings.media_dir)

    semantic_search = False
    if query != "" or table != "":
        if query == "" or table == "":
            raise HTTPException(
                status_code=400,
                detail="Both query and model_name should be provided for semantic search.",
            )
    if table != "":
        semantic_search = True
        if table not in dataset.schema.schemas:
            raise HTTPException(
                status_code=400,
                detail=f"Table {table} not found in dataset {id}.",
            )
        elif not is_view_embedding(dataset.schema.schemas[table]):
            raise HTTPException(
                status_code=400,
                detail=f"Table {table} is not a view embedding table.",
            )
        embedding_table = dataset.open_table(table)

    # Get page parameters
    total = dataset.num_rows
    original_limit = limit
    limit = min(limit, total)

    # Get tables
    table_item = SchemaGroup.ITEM.value
    tables_view = sorted(dataset.schema.groups[SchemaGroup.VIEW])

    # get data (items and views)
    if semantic_search:
        semantic_results: pl.DataFrame = (
            embedding_table.search(query).select(["item_ref.id"]).limit(1e9).to_polars()
        )  # TODO: change high limit if lancedb supports it
        item_results = semantic_results.group_by("item_ref.id").agg(pl.min("_distance")).sort("_distance")
        item_ids = item_results["item_ref.id"].to_list()[skip : skip + limit]

        item_rows = get_rows(dataset, table_item, item_ids)
        item_rows = sorted(item_rows, key=lambda x: item_ids.index(x.id))
    else:
        item_rows = get_rows(dataset, table_item, None, None, limit, skip)

    item_ids = [item.id for item in item_rows]
    item_first_media: dict[str, dict] = {}
    for view in tables_view:
        try:
            view_rows = get_rows(dataset, view, None, item_ids)
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
    rows = []
    for item in item_rows:
        row = {}
        # VIEWS -> thumbnails previews
        for view in tables_view:
            if item_first_media[view][item.id] is not None:
                row[view] = item_first_media[view][item.id].open(dataset.path / "media")
        # ITEM features
        for feat in vars(item).keys():
            row[feat] = getattr(item, feat)
        # DISTANCE
        if semantic_search:
            row["distance"] = item_results.row(by_predicate=(pl.col("item_ref.id") == item.id), named=True)[
                "_distance"
            ]

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
