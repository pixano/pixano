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

from pixano.core import arrow_types
from pixano.core.dataset import Dataset, DatasetInfo, InferenceDataset
from pixano.data import models

from . import db_utils


class Settings(BaseSettings):
    """Dataset library settings

    Attributes:
        data_dir (Path): Dataset library path
    """

    data_dir: Path = Path.cwd() / "library"


def find_dataset(dataset_id: str, settings: Settings) -> dict:
    """Return dataset path and info based on its ID

    Args:
        dataset_id (str): Dataset ID
        settings (Settings): Dataset library

    Returns:
        dict: Dataset path and info
    """

    for info_file in settings.data_dir.glob("*/spec.json"):
        print(info_file)
        info = DatasetInfo.parse_file(info_file)
        if info.id == dataset_id:
            return {"path": info_file.parent, "info": info}
    return None


def load_library(settings: Settings) -> list[DatasetInfo]:
    """Load all dataset info files in library

    Args:
        settings (Settings): Dataset library

    Returns:
        list[DatasetInfo]: Dataset info files
    """

    infos = []
    for info_file in sorted(list(settings.data_dir.glob("*/spec.json"))):
        print(info_file)
        info = DatasetInfo.parse_file(info_file)
        preview = info_file.parent / "preview.png"
        if preview.is_file():
            im = arrow_types.Image(
                uri="preview.png",
                bytes=None,
                preview_bytes=None,
                uri_prefix=info_file.parent,
            )
            info.preview = im.url
        infos.append(info)
    return infos


def load_dataset(dataset_id: str, settings: Settings) -> Dataset:
    """Load dataset based on its ID

    Args:
        dataset_id (str): Dataset ID
        settings (Settings): Dataset library

    Returns:
        Dataset: Dataset
    """

    ds = find_dataset(dataset_id, settings)
    if ds is not None:
        ds = Dataset(ds["path"])
    return ds


def load_dataset_stats(dataset_id: str, settings: Settings) -> dict:
    """Load dataset stats based on its ID

    Args:
        dataset_id (str): Dataset ID
        settings (Settings): Dataset Library

    Returns:
        dict: Dataset stats
    """

    stats = []
    ds = find_dataset(dataset_id, settings)
    if ds:
        stat_file = settings.data_dir / ds["path"].name / "db_feature_statistics.json"
        if stat_file.is_file():
            with open(stat_file, "r") as f:
                stats = json.load(f)
    return stats


def create_app(settings: Settings) -> FastAPI:
    """Run explorer app in library

    Args:
        settings (Settings): Dataset Library

    Raises:
        HTTPException: 404 error if dataset items are not found
        HTTPException: 404 error if dataset stats are not found
        HTTPException: 404 error if dataset item details are not found

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
        library = load_library(settings)
        print(library)
        return library

    @app.get("/datasets/{dataset_id}/items", response_model=Page[models.Features])
    async def get_dataset_items(dataset_id, params: Params = Depends()):
        dataset = load_dataset(dataset_id, settings)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Item not found")
        ds = dataset.load()

        return db_utils.get_items(ds, params)

    @app.get("/datasets/{dataset_id}/stats")
    async def get_dataset_stats(
        dataset_id,
    ):
        stats = load_dataset_stats(dataset_id, settings)
        if stats is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return stats

    @app.get("/datasets/{dataset_id}/items/{id}")
    async def get_dataset_item_details(dataset_id: str, id: str):
        dataset = load_dataset(dataset_id, settings)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Item not found")

        ds = dataset.load()

        # load Inferences datasets
        tmp_ds = find_dataset(
            dataset_id, settings
        )  # ?? more clever way to get tmp_ds["path"].name ??
        infer_datasets = []
        if tmp_ds:
            for info_file in settings.data_dir.glob(
                tmp_ds["path"].name + "/db_*/infer.json"
            ):
                infer_datasets.append(InferenceDataset(info_file.parent).load())

        return db_utils.get_item_details(ds, id, dataset.media_path, infer_datasets)

    add_pagination(app)

    return app


settings = Settings()
app = create_app(settings)
