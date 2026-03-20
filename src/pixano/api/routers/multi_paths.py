# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Multi-paths router."""

from pixano.api.resources import MULTI_PATH_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(MULTI_PATH_RESOURCE)
