# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

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
    app = FastAPI(title="Pixano", version="0.1.0", default_response_class=ORJSONResponse)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
