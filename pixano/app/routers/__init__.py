# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fastapi import FastAPI
from fastapi.routing import APIRouter

from pixano.app.routers.annotations import router as annotations_router
from pixano.app.routers.browser import router as browser_router
from pixano.app.routers.dataset_items import router as dataset_items_router
from pixano.app.routers.datasets import router as datasets_router
from pixano.app.routers.embeddings import router as embeddings_router
from pixano.app.routers.entities import router as entities_router
from pixano.app.routers.inference import router as inference_router
from pixano.app.routers.items import router as items_router
from pixano.app.routers.items_info import router as items_info_router
from pixano.app.routers.models import router as models_router
from pixano.app.routers.sources import router as sources_router
from pixano.app.routers.thumbnail import router as thumbnail_router
from pixano.app.routers.views import router as views_router


API_ROUTERS: tuple[APIRouter, ...] = (
    annotations_router,
    dataset_items_router,
    datasets_router,
    thumbnail_router,
    browser_router,
    embeddings_router,
    entities_router,
    items_router,
    items_info_router,
    sources_router,
    views_router,
    models_router,
    inference_router,
)

API_PREFIXES: tuple[str, ...] = tuple(router.prefix for router in API_ROUTERS if router.prefix)


def include_api_routers(app: FastAPI) -> None:
    """Attach all API routers to the given FastAPI app."""
    for router in API_ROUTERS:
        app.include_router(router)


__all__ = ["API_PREFIXES", "API_ROUTERS", "include_api_routers"]
