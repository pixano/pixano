# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from pixano.__version__ import __version__
from pixano.api.routers import include_api_routers
from pixano.api.settings import Settings


def create_app(settings: Settings = Settings()) -> FastAPI:
    """Create and configure the Pixano app.

    Args:
        settings: App settings.

    Returns:
        The Pixano app.
    """
    # Create app
    app = FastAPI(title="Pixano", version=__version__, default_response_class=ORJSONResponse)

    # Boot recovery: replay interrupted staging journals and mark orphaned
    # import jobs as interrupted (spec §8/§9).
    if isinstance(settings.library_dir, Path) and settings.library_dir.name == "library":
        try:
            from pixano.datasets.io.jobs import boot_recover

            boot_recover(settings.library_dir.parent)
        except Exception:  # pragma: no cover - recovery must never block boot
            logging.getLogger(__name__).warning("Data IO boot recovery failed", exc_info=True)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Mount models folder
    if settings.models_dir is None:
        raise FileNotFoundError("Model directory not provided")
    if not settings.models_dir.exists():
        settings.models_dir.mkdir(exist_ok=True)
    app.mount(
        "/app_models",
        StaticFiles(directory=settings.models_dir),
        name="models",
    )

    # Health endpoint
    @app.get("/health", tags=["Health"], operation_id="health_check")
    def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    # Include routers
    include_api_routers(app)

    return app
