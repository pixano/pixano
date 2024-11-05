# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.app.models import ItemInfoModel, ItemModel
from pixano.app.settings import Settings, get_settings
from pixano.datasets.queries import TableQueryBuilder
from pixano.datasets.utils import DatasetAccessError, DatasetPaginationError
from pixano.features.schemas.schema_group import SchemaGroup
from pixano.utils.python import to_sql_list

from .utils import (
    assert_table_in_group,
    get_dataset,
    get_models_from_rows,
    get_rows,
)


router = APIRouter(prefix="/items_info", tags=["Items"])


@router.get("/{dataset_id}/", response_model=list[ItemInfoModel])
async def get_items_info(
    dataset_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    where: str | None = None,
    ids: list[str] | None = Query(None),
    limit: int | None = None,
    skip: int = 0,
) -> list[ItemInfoModel]:
    """Get items info.

    Args:
        dataset_id: Dataset ID.
        settings: App settings.
        where: Where clause for the item table.
        ids: IDs.
        limit: Limit number of items.
        skip: Skip number of items.

    Returns:
        List of items info.
    """
    dataset = get_dataset(dataset_id, settings.library_dir, None)
    assert_table_in_group(dataset, SchemaGroup.ITEM.value, SchemaGroup.ITEM)

    try:
        item_rows = get_rows(dataset, SchemaGroup.ITEM.value, where, ids, None, limit, skip)
    except DatasetPaginationError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except DatasetAccessError as err:
        raise HTTPException(status_code=500, detail=str(err))

    items_models = get_models_from_rows(SchemaGroup.ITEM.value, ItemModel, item_rows)
    item_models_identified = {item.id: item for item in items_models}

    set_ids = {item.id for item in items_models}
    infos = {
        id: {
            group.value: {table: {"count": 0} for table in tables}
            for group, tables in dataset.schema.groups.items()
            if group.value not in [SchemaGroup.EMBEDDING.value, SchemaGroup.ITEM.value]
        }
        for id in set_ids
    }

    for table_name, table in dataset.open_tables().items():
        group_name = dataset.schema.get_table_group(table_name).value
        if group_name in [SchemaGroup.EMBEDDING.value, SchemaGroup.ITEM.value]:
            continue
        sql_ids = to_sql_list(set_ids)
        df: pd.DataFrame = (
            TableQueryBuilder(table).select(["item_ref.id"]).where(f"item_ref.id in {sql_ids}").to_pandas()
        )
        for id, count in df["item_ref.id"].value_counts().to_dict().items():
            infos[id][group_name][table_name] = {"count": count}

    items_info = [ItemInfoModel(info=info, **item_models_identified[id].model_dump()) for id, info in infos.items()]

    return items_info


@router.get("/{dataset_id}/{id}", response_model=ItemInfoModel)
async def get_item_info(
    dataset_id: str, id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> ItemInfoModel:
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
