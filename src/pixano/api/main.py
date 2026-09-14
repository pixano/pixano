# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anyio.to_thread
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from s3path import S3Path
from starlette.middleware.gzip import GZipMiddleware

from pixano.__version__ import __version__
from pixano.api.jobs.events import EventBroker
from pixano.api.routers import include_api_routers
from pixano.api.settings import Settings
from pixano.datasets.utils.errors import DatasetBusyError


# Media blobs are already compressed (JPEG/PNG/MP4); running them through gzip
# burns request-thread CPU (which competes with background import jobs) for no
# size win. Bypass by route shape — cheaper than sniffing content types.
_GZIP_BYPASS_SUFFIXES = ("/blob", "/preview")
_GZIP_BYPASS_SEGMENTS = ("/sframes/batch", "/media/")


class SelectiveGZipMiddleware(GZipMiddleware):
    """GZip that leaves blob and frame-stream routes uncompressed."""

    async def __call__(self, scope, receive, send):
        """Bypass compression for media routes; defer to gzip elsewhere."""
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path.endswith(_GZIP_BYPASS_SUFFIXES) or any(seg in path for seg in _GZIP_BYPASS_SEGMENTS):
                await self.app(scope, receive, send)
                return
        await super().__call__(scope, receive, send)


def _lifespan(settings: Settings):
    """Build the app lifespan: a wider threadpool, and the job event listener."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Raise the sync-endpoint threadpool above anyio's 40-token default.

        Every data endpoint is sync `def`, and blob/frame downloads hold a token
        for their full duration — a gallery plus a video workspace plus job polling
        exhausts 40 while a background import competes for CPU.

        The job event listener starts here so that one connection serves every open
        stream, instead of one per browser tab.
        """
        anyio.to_thread.current_default_thread_limiter().total_tokens = 100
        broker = EventBroker(settings.database_url)
        broker.start()
        app.state.job_events = broker
        try:
            yield
        finally:
            await broker.stop()

    return lifespan


def create_app(settings: Settings = Settings()) -> FastAPI:
    """Create and configure the Pixano app.

    Args:
        settings: App settings.

    Returns:
        The Pixano app.
    """
    # Create app
    app = FastAPI(
        title="Pixano",
        version=__version__,
        default_response_class=JSONResponse,
        lifespan=_lifespan(settings),
    )

    @app.exception_handler(DatasetBusyError)
    async def dataset_busy_handler(_request, error: DatasetBusyError):
        return JSONResponse(status_code=409, content={"detail": {"code": error.code, "message": str(error)}})

    # Boot recovery: replay interrupted staging journals and mark orphaned
    # import jobs as interrupted (spec §8/§9).
    if (
        isinstance(settings.library_dir, Path)
        and not isinstance(settings.library_dir, S3Path)
        and settings.library_dir.name == "library"
    ):
        try:
            from pixano.datasets.io.jobs import boot_recover

            boot_recover(settings.library_dir.parent)
        except Exception:  # pragma: no cover - recovery must never block boot
            logging.getLogger(__name__).warning("Data IO boot recovery failed", exc_info=True)
    app.add_middleware(SelectiveGZipMiddleware, minimum_size=500)
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
        settings.models_dir.mkdir(parents=True, exist_ok=True)
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
