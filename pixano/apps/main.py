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


from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import Page, Params
from fastapi_pagination.api import add_pagination

from pixano.api import (
    ItemFeatures,
    Settings,
    load_dataset,
    load_dataset_stats,
    load_item_details,
    load_item_embedding,
    load_items,
    load_library,
    save_item_annotations,
)
from pixano.data import DatasetInfo, EmbeddingDataset, InferenceDataset
from pixano.types import ObjectAnnotation


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

    @app.get("/datasets/{ds_id}/items", response_model=Page[ItemFeatures])
    async def get_dataset_items(ds_id, params: Params = Depends()):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        # Return dataset items
        res = load_items(ds, params)
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
            inf_datasets.append(InferenceDataset(inf_json.parent))

        # Return item details
        return load_item_details(ds, item_id, ds.media_dir, inf_datasets)

    @app.post("/datasets/{ds_id}/items/{item_id}/{view}/embedding")
    async def get_dataset_item_view_embedding(ds_id: str, item_id: str, view: str):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Load embedding dataset (currently selecting latest one)
        emb_ds = None
        for emb_json in sorted(list(ds.path.glob("db_embed_*/embed.json"))):
            emb_ds = EmbeddingDataset(emb_json.parent)
        if emb_ds is None:
            raise HTTPException(status_code=404, detail="Embedding dataset not found")

        # Return item embedding
        return Response(content=load_item_embedding(emb_ds, item_id, view))

    @app.post(
        "/datasets/{ds_id}/items/{item_id}/annotations",
        response_model=list[ObjectAnnotation],
    )
    async def post_dataset_item_annotations(
        ds_id: str,
        item_id: str,
        annotations: list[ObjectAnnotation],
    ):
        # Load dataset
        ds = load_dataset(ds_id, settings)
        if ds is None:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Update dataset annotations
        save_item_annotations(ds.path, item_id, annotations)

        return Response()

    add_pagination(app)

    return app


def app():
    settings = Settings()
    return create_app(settings)
