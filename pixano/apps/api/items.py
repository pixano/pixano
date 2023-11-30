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

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page, resolve_params

from pixano.data import Dataset, DatasetItem, Settings

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

    # Load dataset
    dataset = Dataset.find(ds_id, get_settings().data_dir)

    if dataset:
        # Get page parameters
        params = resolve_params(params)
        raw_params = params.to_raw_params()
        total = dataset.num_rows

        # Check page parameters
        start = raw_params.offset
        stop = min(raw_params.offset + raw_params.limit, total)
        if start >= stop:
            raise HTTPException(status_code=404, detail="Invalid page parameters")

        # Load dataset items
        items = dataset.load_items(raw_params.limit, raw_params.offset)

        # Return dataset items
        if items:
            return create_page(items, total=total, params=params)
        else:
            raise HTTPException(status_code=404, detail="Dataset item not found")
    else:
        raise HTTPException(status_code=404, detail="Dataset not found")


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

    # Load dataset
    dataset = Dataset.find(ds_id, get_settings().data_dir)

    if dataset:
        # Get page parameters
        params = resolve_params(params)
        raw_params = params.to_raw_params()
        total = dataset.num_rows

        # Check page parameters
        start = raw_params.offset
        stop = min(raw_params.offset + raw_params.limit, total)
        if start >= stop:
            raise HTTPException(status_code=404, detail="Invalid page parameters")

        # Load dataset items
        items = dataset.search_items(raw_params.limit, raw_params.offset, query)

        # Return dataset items
        if items:
            return create_page(items, total=total, params=params)
        else:
            raise HTTPException(status_code=404, detail="Dataset item not found")
    else:
        raise HTTPException(status_code=404, detail="Dataset not found")


@router.get("/items/{item_id}", response_model=DatasetItem)
async def get_dataset_item(ds_id: str, item_id: str) -> DatasetItem:
    """Load dataset item

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID

    Returns:
        DatasetItem: Dataset item
    """

    # Load dataset
    dataset = Dataset.find(ds_id, get_settings().data_dir)

    if dataset:
        # Load dataset item
        item = dataset.load_item(item_id, load_objects=True)

        # Return dataset item
        if item:
            return item
        else:
            raise HTTPException(status_code=404, detail="Dataset item not found")
    else:
        raise HTTPException(status_code=404, detail="Dataset not found")


@router.post("/items/{item_id}", response_model=DatasetItem)
async def post_dataset_item(ds_id: str, item: DatasetItem):
    """Save dataset item

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID
    """

    # Load dataset
    dataset = Dataset.find(ds_id, get_settings().data_dir)

    if dataset:
        # Save dataset item
        dataset.save_item(item)

        # Return response
        return Response()
    else:
        raise HTTPException(status_code=404, detail="Dataset not found")


@router.get(
    "/items/{item_id}/embeddings/{model_id}",
    response_model=DatasetItem,
)
async def get_item_embeddings(ds_id: str, item_id: str, model_id: str) -> DatasetItem:
    """Load dataset item embeddings

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID
        model_id (str): Model ID
    """

    # Load dataset
    dataset = Dataset.find(ds_id, get_settings().data_dir)

    if dataset:
        item = dataset.load_item(
            item_id,
            load_media=False,
            load_active_learning=False,
            load_embeddings=True,
            model_id=model_id,
        )

        # Return dataset item embeddings
        if item:
            return item
        else:
            raise HTTPException(
                status_code=404, detail="Dataset item embeddings not found"
            )
    else:
        raise HTTPException(status_code=404, detail="Dataset not found")
