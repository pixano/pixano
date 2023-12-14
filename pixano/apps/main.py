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

from s3path import S3Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination.api import add_pagination

from pixano.apps.api import datasets, items, models
from pixano.data import Settings


def create_app(settings: Settings = Settings()) -> FastAPI:
    """Run Pixano app

    Args:
        settings (Settings, optional): Settings containing dataset library path. Defaults to empty Settings().

    Returns:
        FastAPI: Pixano App
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

    # Create models directory
    model_dir = settings.data_dir / "models"
    model_dir.mkdir(exist_ok=True)

    if not isinstance(settings.data_dir, S3Path):
        # Mount data directory (datasets + models)
        app.mount(
            "/data",
            StaticFiles(directory=settings.data_dir),
            name="data",
        )
    else:
        # don't need to mount dataset, but still need to mount model
        if settings.local_model_dir is None:
            # try to get model from S3 /models
            #TODO
            # list models in settings.data_dir / "models"
            # dl them locally (where ??) and use this as mount point
            # settings.local_model_dir = (settings.data_dir / "models").open()
            raise Exception("download models from S3 not implemented yet, please set LOCAL_MODEL_DIR env var to a path with /models/<sam_model.onnx>)")
        else:
            # use local model
            app.mount(
                "/data",
                StaticFiles(directory=settings.local_model_dir),
                name="data",
            )

    app.include_router(datasets.router)
    app.include_router(items.router)
    app.include_router(models.router)

    add_pagination(app)
    return app
