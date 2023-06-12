# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import Page, Params
from fastapi_pagination.api import add_pagination
from pydantic import BaseSettings

from pixano.core import Dataset, DatasetInfo, InferenceDataset, arrow_types
from pixano.data import models

from . import db_utils


class Settings(BaseSettings):
    """Dataset library settings

    Attributes:
        data_dir (Path): Dataset library directory
    """

    data_dir: Path = Path.cwd() / "library"


def load_library(settings: Settings) -> list[DatasetInfo]:
    """Load all dataset info files in library

    Args:
        settings (Settings): Dataset library settings

    Returns:
        list[DatasetInfo]: Dataset info files
    """

    infos = []
    for spec in sorted(settings.data_dir.glob("*/spec.json")):
        # Load dataset info
        info = DatasetInfo.parse_file(spec)
        # Load preview.png
        preview = spec.parent / "preview.png"
        if preview.is_file():
            im = arrow_types.Image(
                uri="preview.png",
                bytes=None,
                preview_bytes=None,
                uri_prefix=spec.parent,
            )
            info.preview = im.url
        # Save dataset info
        infos.append(info)
    return infos


def load_dataset(ds_id: str, settings: Settings) -> Dataset:
    """Load dataset based on its ID

    Args:
        ds_id (str): Dataset ID
        settings (Settings): Dataset library

    Returns:
        Dataset: Dataset
    """

    for spec in settings.data_dir.glob("*/spec.json"):
        info = DatasetInfo.parse_file(spec)
        if ds_id == info.id:
            return Dataset(spec.parent)


def load_dataset_stats(ds_id: str, settings: Settings) -> dict:
    """Load dataset stats based on its ID

    Args:
        ds_id (str): Dataset ID
        settings (Settings): Dataset Library

    Returns:
        list[dict]: Dataset stats
    """

    ds = load_dataset(ds_id, settings)
    if ds is not None:
        stats_file = ds.path / "db_feature_statistics.json"
        if stats_file.is_file():
            with open(stats_file, "r") as f:
                return json.load(f)


def create_app(settings: Settings) -> FastAPI:
    """Run explorer app in library

    Args:
        settings (Settings): Dataset Library

    Raises:
        HTTPException: 404, Dataset is not found
        HTTPException: 404, Dataset stats are not found
        HTTPException: 404, Dataset is not found

    Returns:
        FastAPI: Explorer app
    """
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/datasets", response_model=list[DatasetInfo])
    async def get_datasets_list():
        return load_library(settings)

    @app.get("/datasets/{ds_id}/items", response_model=Page[models.Features])
    async def get_dataset_items(ds_id, params: Params = Depends()):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        # Return dataset items
        return db_utils.get_items(ds.load(), params)

    @app.get("/datasets/{ds_id}/stats")
    async def get_dataset_stats(ds_id):
        # Load dataset stats
        stats = load_dataset_stats(ds_id, settings)
        if stats is None:
            raise HTTPException(status_code=404, detail="Stats not found")
        # Return dataset stats
        return stats

    @app.get("/datasets/{ds_id}/items/{item_id}")
    async def get_dataset_item_details(ds_id: str, item_id: str):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Load inference datasets
        inf_datasets = []
        for inf_json in sorted(list(ds.path.glob("db_infer_*/infer.json"))):
            inf_datasets.append(InferenceDataset(inf_json.parent).load())

        # Return item details
        return db_utils.get_item_details(ds.load(), item_id, ds.media_dir, inf_datasets)

    add_pagination(app)

    return app


settings = Settings()
app = create_app(settings)
