# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination.api import add_pagination
from s3path import S3Path

from pixano.app.api import datasets, items, models
from pixano.app.settings import Settings


def create_app(settings: Settings = Settings()) -> FastAPI:
    """Run Pixano app.

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
            raise FileNotFoundError(f"Local model directory '{settings.model_dir.absolute()}' not found")
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
            raise FileNotFoundError(f"Dataset library '{settings.data_dir.absolute()}' not found")
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
