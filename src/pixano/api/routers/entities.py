"""Entities router."""

from pixano.api.resources import ENTITY_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(ENTITY_RESOURCE)
