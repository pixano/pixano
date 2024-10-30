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
from pixano.app.routers.sources import router as sources_router
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
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount folders
    if isinstance(settings.library_dir, S3Path):
        # If S3, mount models parent folder
        # Check if folder exists
        if settings.models_dir is None:
            raise FileNotFoundError("Local model directory not provided")
        elif not settings.models_dir.exists():
            raise FileNotFoundError(f"Local model directory '{settings.models_dir.absolute()}' not found")
        # Mount
        app.mount(
            "/data",
            StaticFiles(directory=settings.models_dir.parent),
            name="data",
        )
    else:
        # If local, mount datasets folder with models subfolder
        # Check if folder exists
        if not settings.library_dir.exists():
            raise FileNotFoundError(f"Dataset library '{settings.library_dir.absolute()}' not found")
        # Create models subfolder in case it doesn't exist yet
        if settings.models_dir is not None and not settings.models_dir.exists():
            settings.models_dir.mkdir(exist_ok=True)
        # Mount
        app.mount(
            "/data",
            StaticFiles(directory=settings.library_dir),
            name="data",
        )
        print("MOUNT MEDIA DIR on /media:", settings.media_dir)
        app.mount(
            "/media",
            StaticFiles(directory=settings.media_dir),
            name="media",
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
    app.include_router(sources_router)
    app.include_router(views_router)

    return app
