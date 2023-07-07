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

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import Page, Params
from fastapi_pagination.api import add_pagination
from pydantic import BaseSettings

from pixano.core import (
    Dataset,
    DatasetInfo,
    EmbeddingDataset,
    InferenceDataset,
    arrow_types,
)

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
        # Load thumbnail
        preview_path = spec.parent / "preview.png"
        if preview_path.is_file():
            im = arrow_types.Image(uri=preview_path.absolute().as_uri())
            info.preview = im.url

        # Load categories
        info.categories = getattr(info, "categories", [])
        if info.categories is None:
            info.categories = []
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
    """Run Pixano app

    Args:
        settings (Settings): Dataset Library

    Raises:
        HTTPException: 404, Dataset is not found
        HTTPException: 404, Dataset stats are not found
        HTTPException: 404, Dataset is not found
        HTTPException: 404, Dataset is not found
        HTTPException: 404, Embedding dataset is not found

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

    # Check if library exists
    if not settings.data_dir.exists():
        raise FileNotFoundError(
            f"Dataset library '{settings.data_dir.absolute()}' not found"
        )

    # Create models folder
    model_dir = settings.data_dir / "models"
    model_dir.mkdir(exist_ok=True)
    app.mount("/models", StaticFiles(directory=model_dir), name="models")

    @app.get("/datasets", response_model=list[DatasetInfo])
    async def get_datasets_list():
        return load_library(settings)

    @app.get("/datasets/{ds_id}/items", response_model=Page[db_utils.Features])
    async def get_dataset_items(ds_id, params: Params = Depends()):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        # Return dataset items
        res = db_utils.get_items(ds.load(), params)
        if res is None:
            raise HTTPException(status_code=404, detail="Data not found")
        else:
            return res

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

    @app.post("/datasets/{ds_id}/items/{item_id}/{view}/embedding")
    async def get_dataset_item_view_embedding(ds_id: str, item_id: str, view: str):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Load embedding dataset (currently selecting latest one)
        emb_ds = None
        for emb_json in sorted(list(ds.path.glob("db_embed_*/embed.json"))):
            emb_ds = EmbeddingDataset(emb_json.parent).load()
        if emb_ds is None:
            raise HTTPException(status_code=404, detail="Embedding dataset not found")

        # Return item embedding
        return Response(content=db_utils.get_item_view_embedding(emb_ds, item_id, view))

    @app.post(
        "/datasets/{ds_id}/items/{item_id}/annotations",
        response_model=list[arrow_types.ObjectAnnotation],
    )
    async def post_dataset_item_annotations(
        ds_id: str,
        item_id: str,
        annotations: list[arrow_types.ObjectAnnotation],
    ):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Update dataset annotations
        db_utils.update_annotations(ds.path, item_id, annotations)

        return Response()

    add_pagination(app)

    return app


def app():
    settings = Settings()
    return create_app(settings)
