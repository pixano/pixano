"""Records router."""

from pixano.api.resources import RECORD_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(RECORD_RESOURCE)
