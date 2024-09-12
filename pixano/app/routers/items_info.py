# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models import ItemInfo, ItemModel
from pixano.app.settings import Settings, get_settings
from pixano.features.schemas.schema_group import SchemaGroup
from pixano.datasets import DatasetPaginationError, DatasetAccessError

from .utils import (
    assert_table_in_group,
    get_dataset,
    get_models_from_rows,
    get_model_from_row,
    get_rows,
    get_row,
)

router = APIRouter(prefix="/items_info", tags=["Items"])


@router.get("/{dataset_id}/", response_model=list[ItemInfo])
async def get_items_info(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[ItemInfo]:
    """Get items info.

    Args:
        dataset_id: Dataset ID.
        settings: App settings.
        ids: IDs.
        item_ids: Item IDs.
        limit: Limit number of items.
        skip: Skip number of items.

    Returns:
        List of items info.
    """

    dataset = get_dataset(dataset_id, settings.data_dir, None)
    assert_table_in_group(dataset, SchemaGroup.ITEM.value, SchemaGroup.ITEM)
    
    try:
        item_rows = get_rows(dataset, SchemaGroup.ITEM.value, ids, None, limit, skip)
    except DatasetPaginationError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except DatasetAccessError as err:
        raise HTTPException(status_code=500, detail=str(err))
    
    items_models = get_models_from_rows(SchemaGroup.ITEM.value, ItemModel, item_rows)
    item_models_identified = {item.id: item for item in items_models}

    set_ids = {item.id for item in items_models}
    infos = {
        id: {group.value: {table: {"count":0} for table in tables} for group, tables in dataset.schema.groups.items()}
        for id in set_ids
    }

    for table_name, table in dataset.open_tables().items():
        group_name = dataset.schema.get_table_group(table_name).value
        if table_name == SchemaGroup.ITEM.value:
            continue
        sql_ids = f"('{list(set_ids)[0]}')" if len(set_ids) == 1 else str(tuple(set_ids))
        df: pd.DataFrame = table.search().select(["item_ref.id"]).where(f"item_ref.id in {sql_ids}").to_pandas()
        for id, count in df["item_ref.id"].value_counts().to_dict().items():
            infos[id][group_name][table_name] = {"count": count }
    
    items_info = [ItemInfo(info=info, **item_models_identified[id].model_dump()) for id, info in infos.items()]

    return items_info



@router.get("/{dataset_id}/{id}", response_model=ItemInfo)
async def get_item_info(
    dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> ItemInfo:
    """Get an item info.

    Args:
        dataset_id: Dataset ID.
        id: ID.
        settings: App settings.

    Returns:
        The item info.
    """
        
    items_info = await get_items_info(dataset_id=dataset_id, settings=settings, ids=[id], limit=None, skip=0)
    
    return items_info[0]
