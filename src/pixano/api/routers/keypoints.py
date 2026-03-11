"""KeyPoints router."""

from pixano.api.resources import KEYPOINTS_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(KEYPOINTS_RESOURCE)
