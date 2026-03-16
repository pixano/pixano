# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""BBoxes router."""

from pixano.api.resources import BBOX_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(BBOX_RESOURCE)
