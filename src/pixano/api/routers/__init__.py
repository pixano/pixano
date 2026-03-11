# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fastapi import FastAPI
from fastapi.routing import APIRouter

from pixano.api.routers.bboxes import router as bboxes_router
from pixano.api.routers.conversations import router as conversations_router
from pixano.api.routers.datasets import router as datasets_router
from pixano.api.routers.embeddings import router as embeddings_router
from pixano.api.routers.entities import router as entities_router
from pixano.api.routers.entity_dynamic_states import router as entity_dynamic_states_router
from pixano.api.routers.keypoints import router as keypoints_router
from pixano.api.routers.masks import router as masks_router
from pixano.api.routers.messages import router as messages_router
from pixano.api.routers.records import router as records_router
from pixano.api.routers.text_spans import router as text_spans_router
from pixano.api.routers.tracklets import router as tracklets_router
from pixano.api.routers.views import router as views_router


RESOURCE_ROUTERS: tuple[APIRouter, ...] = (
    records_router,
    views_router,
    entities_router,
    entity_dynamic_states_router,
    tracklets_router,
    bboxes_router,
    masks_router,
    keypoints_router,
    messages_router,
    conversations_router,
    text_spans_router,
    embeddings_router,
)

API_ROUTERS: tuple[APIRouter, ...] = (
    datasets_router,
    *RESOURCE_ROUTERS,
)

API_PREFIXES: tuple[str, ...] = tuple(dict.fromkeys(router.prefix for router in API_ROUTERS if router.prefix))


def include_api_routers(app: FastAPI) -> None:
    """Attach all active API routers to the given FastAPI app."""

    for router in API_ROUTERS:
        app.include_router(router)


__all__ = ["API_PREFIXES", "API_ROUTERS", "RESOURCE_ROUTERS", "include_api_routers"]
