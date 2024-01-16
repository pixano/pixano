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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination.api import add_pagination
from s3path import S3Path

from pixano.app.api import datasets, items, models
from pixano.data.settings import Settings


def create_app(settings: Settings = Settings()) -> FastAPI:
    """Run Pixano app

    Args:
        settings (Settings): App settings

    Returns:
        FastAPI: Pixano app
    """

    # Create app
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount folders
    if isinstance(settings.data_dir, S3Path):
        # If S3, mount models parent folder
        # Check if folder exists
        if not settings.model_dir.exists():
            raise FileNotFoundError(
                f"Local model directory '{settings.model_dir.absolute()}' not found"
            )
        # Mount
        app.mount(
            "/data",
            StaticFiles(directory=settings.model_dir.parent),
            name="data",
        )
    else:
        # If local, mount datasets folder with models subfolder
        # Check if folder exists
        if not settings.data_dir.exists():
            raise FileNotFoundError(
                f"Dataset library '{settings.data_dir.absolute()}' not found"
            )
        # Create models subfolder in case it doesn't exist yet
        settings.model_dir.mkdir(exist_ok=True)
        # Mount
        app.mount(
            "/data",
            StaticFiles(directory=settings.data_dir),
            name="data",
        )

    app.include_router(datasets.router)
    app.include_router(items.router)
    app.include_router(models.router)

    add_pagination(app)
    return app
