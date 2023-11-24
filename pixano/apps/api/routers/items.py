# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page

from pixano.data import DatasetItem, ItemEmbedding, Settings

# TMP: Mock data
from .mock_data import item_embeddings, items

router = APIRouter(tags=["items"], prefix="/datasets/{ds_id}")


@lru_cache
def get_settings() -> Settings:
    """Get app settings

    Returns:
        Settings: App settings
    """

    return Settings()


@router.get("/items", response_model=Page[DatasetItem])
async def get_dataset_items(
    ds_id: str,
    params: Params = Depends(),
) -> Page[DatasetItem]:
    """Load dataset items

    Args:
        ds_id (str): Dataset ID
        params (Params, optional): Pagination parameters (offset and limit). Defaults to Depends().

    Returns:
        Page[DatasetItem]: Dataset items page
    """

    # TMP: Mock data
    total = len(items[ds_id])
    if total > 0:
        return create_page(list(items[ds_id].values()), total=total, params=params)
    else:
        raise HTTPException(status_code=404, detail="Items not found")


@router.get("/search", response_model=Page[DatasetItem])
async def search_dataset_items(
    ds_id: str,
    query: dict[str, str],
    params: Params = Depends(),
) -> Page[DatasetItem]:
    """Load dataset items with a query

    Args:
        ds_id (str): Dataset ID
        query (dict[str, str]): Search query
        params (Params, optional): Pagination parameters (offset and limit). Defaults to Depends().

    Returns:
        Page[DatasetItem]: Dataset items page
    """

    # TMP: Mock data
    total = len(items[ds_id])
    if total > 0:
        return create_page(list(items[ds_id].values()), total=total, params=params)
    else:
        raise HTTPException(status_code=404, detail="Items not found")


@router.get("/items/{item_id}", response_model=DatasetItem)
async def get_dataset_item(ds_id: str, item_id: str) -> DatasetItem:
    """Load dataset item

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID

    Returns:
        DatasetItem: Dataset item
    """

    # TMP: Mock data
    if item_id in items[ds_id]:
        return items[ds_id][item_id]
    else:
        raise HTTPException(status_code=404, detail="Item not found")


@router.post("/items/{item_id}", response_model=DatasetItem)
async def post_dataset_item(ds_id: str, item_id: str, item: DatasetItem):
    """Save dataset item

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID
    """

    # TODO: Mock data
    pass


@router.get(
    "/items/{item_id}/embeddings/{model_id}",
    response_model=list[ItemEmbedding],
)
async def get_item_embeddings(
    ds_id: str, item_id: str, model_id: str
) -> list[ItemEmbedding]:
    """Load dataset item embeddings

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID
        model_id (str): Model ID
    """

    # TMP: Mock data
    if (
        model_id in item_embeddings[ds_id]
        and item_id in item_embeddings[ds_id][model_id]
    ):
        return item_embeddings[ds_id][model_id][item_id]
    else:
        raise HTTPException(status_code=404, detail="Embeddings not found")
