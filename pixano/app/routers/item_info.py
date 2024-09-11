# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

import pandas as pd
from fastapi import Depends, Query

from pixano.app.models import ItemInfo, ItemModel
from pixano.app.settings import Settings, get_settings
from pixano.datasets.dataset import _validate_ids_item_ids_and_limit_and_skip
from pixano.features.schemas.schema_group import SchemaGroup

from .items import router
from .utils import (
    get_dataset,
    get_models_from_rows,
    get_rows,
)


@router.get("/info/{dataset_id}", response_model=list[ItemInfo])
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
    _validate_ids_item_ids_and_limit_and_skip(ids, limit, skip, None)
    dataset = get_dataset(dataset_id, settings.data_dir, None)

    items = get_rows(dataset, SchemaGroup.ITEM.value, ids, None, limit, skip)
    items_models = get_models_from_rows(SchemaGroup.ITEM.value, ItemModel, items)
    item_models_identified = {item.id: item for item in items_models}
    set_ids = {item.id for item in items_models}
    infos = {
        id: {group.value: {table: 0 for table in tables} for group, tables in dataset.schema.groups.items()}
        for id in set_ids
    }

    for table_name, table in dataset.open_tables().items():
        sql_ids = f"('{list(set_ids)[0]}')" if len(set_ids) == 1 else str(tuple(set_ids))
        df: pd.DataFrame = table.search().select("item_id").where(f"item_id in {sql_ids}")
        for id, count in df["item_id"].value_counts().to_dict().items():
            infos[id][dataset.schema.get_table_group(table_name).value][table_name] = count
    items_info = [ItemInfo(id=id, infos=info, data=item_models_identified[id]) for id, info in infos.items()]

    return items_info
