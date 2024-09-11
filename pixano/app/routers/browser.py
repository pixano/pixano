# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination import Params
from fastapi_pagination.api import resolve_params

from pixano.app.models import DatasetBrowser, PaginationColumn, PaginationInfo, TableData
from pixano.app.settings import Settings, get_settings
from pixano.features.schemas.schema_group import _SchemaGroup

from .utils import get_dataset as get_dataset_utils
from .utils import get_rows


router = APIRouter(prefix="/browser", tags=["Browser"])


@router.get("/{id}", response_model=DatasetBrowser)
async def get_browser(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    params: Params = Depends(),
) -> DatasetBrowser:  # type: ignore
    """## Load dataset items for Explorer page.

    Args:
        id: Dataset ID.
        settings: App settings.
        params: Pagination parameters (offset and limit).

    Returns:
        Dataset explorer page.
    """
    # Load dataset
    dataset = get_dataset_utils(id, settings.data_dir, None)

    if dataset:
        # Get page parameters
        params = resolve_params(params)
        raw_params = params.to_raw_params()
        total = dataset.num_rows
        skip = raw_params.offset
        limit = min(raw_params.limit, total)

        # Get tables
        table_item = next(iter(dataset.schema.groups[_SchemaGroup.ITEM]))
        tables_view = dataset.schema.groups[_SchemaGroup.VIEW]

        # get data (items and views)
        item_rows = get_rows(dataset, table_item, None, None, limit, skip)
        item_ids = [item.id for item in item_rows]
        item_first_media: dict[str, dict] = {}
        for view in tables_view:
            view_rows = get_rows(dataset, view, None, item_ids)
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

            rows.append(row)

        # Return dataset items
        return DatasetBrowser(
            id=id,
            name=dataset.info.name,
            table_data=TableData(cols=cols, rows=rows),
            pagination=PaginationInfo(current=skip, size=raw_params.limit, total=total),
            semantic_search=["CLIP", "BLIP2"],
        )
        raise HTTPException(
            status_code=404,
            detail=(f"No items found with page parameters (start {skip}, " f"stop {raw_params.limit}) in dataset",),
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {id} not found in {settings.data_dir.absolute()}",
    )
