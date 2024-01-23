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

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page, resolve_params

from pixano.data import Dataset, DatasetItem, Settings, get_settings

router = APIRouter(tags=["items"], prefix="/datasets/{ds_id}")


@router.get("/items", response_model=Page[DatasetItem])
async def get_dataset_items(
    ds_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
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
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        # Get page parameters
        params = resolve_params(params)
        raw_params = params.to_raw_params()
        total = dataset.num_rows

        # Check page parameters
        start = raw_params.offset
        stop = min(raw_params.offset + raw_params.limit, total)
        if start >= stop:
            raise HTTPException(
                status_code=404,
                detail=f"Invalid page parameters (start {start}, stop {stop})",
            )

        # Load dataset items
        items = dataset.load_items(raw_params.limit, raw_params.offset)

        # Return dataset items
        if items:
            return create_page(items, total=total, params=params)
        raise HTTPException(
            status_code=404,
            detail=f"No items found with page parameters (start {start}, stop {stop}) in dataset",
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.post("/search", response_model=Page[DatasetItem])
async def search_dataset_items(
    ds_id: str,
    query: dict[str, str],
    settings: Annotated[Settings, Depends(get_settings)],
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
    dataset = Dataset.find(ds_id, settings.data_dir)

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
        raise HTTPException(
            status_code=404, detail=f"No items found for query '{query}' in dataset"
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.get("/items/{item_id}", response_model=DatasetItem)
async def get_dataset_item(
    ds_id: str,
    item_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetItem:
    """Load dataset item

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID

    Returns:
        DatasetItem: Dataset item
    """

    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        # Load dataset item
        item = dataset.load_item(item_id, load_objects=True)

        # Return dataset item
        if item:
            return item
        raise HTTPException(
            status_code=404,
            detail=f"Item '{item_id}' not found in dataset",
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.post("/items/{item_id}", response_model=DatasetItem)
async def post_dataset_item(
    ds_id: str,
    item: DatasetItem,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Save dataset item

    Args:
        ds_id (str): Dataset ID
        item (DatasetItem): Item to save
    """

    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        # Save dataset item
        dataset.save_item(item)

        # Return response
        return Response()
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.get(
    "/items/{item_id}/embeddings/{model_id}",
    response_model=DatasetItem,
)
async def get_item_embeddings(
    ds_id: str,
    item_id: str,
    model_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetItem:
    """Load dataset item embeddings

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID
        model_id (str): Model ID (ONNX file path)
    """

    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

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
        raise HTTPException(
            status_code=404,
            detail=f"No embeddings found for item '{item_id}' with model '{model_id}' in dataset",
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )
