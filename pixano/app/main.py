# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from s3path import S3Path

from pixano.app.routers.annotations import router as annotations_router
from pixano.app.routers.browser import router as browser_router
from pixano.app.routers.dataset_items import router as dataset_items_router
from pixano.app.routers.datasets import router as datasets_router
from pixano.app.routers.embeddings import router as embeddings_router
from pixano.app.routers.entities import router as entities_router
from pixano.app.routers.items import router as items_router
from pixano.app.routers.items_info import router as items_info_router
from pixano.app.routers.views import router as views_router
from pixano.app.settings import Settings


def create_app(settings: Settings = Settings()) -> FastAPI:
    """Run Pixano app.

    Args:
        settings: App settings.

    Returns:
        Pixano app.
    """
    # Create app
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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

    # Include routers
    app.include_router(annotations_router)
    app.include_router(dataset_items_router)
    app.include_router(datasets_router)
    app.include_router(browser_router)
    app.include_router(embeddings_router)
    app.include_router(entities_router)
    app.include_router(items_router)
    app.include_router(items_info_router)
    app.include_router(views_router)

    return app
