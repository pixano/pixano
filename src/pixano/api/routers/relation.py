# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Relations router."""

from pixano.api.resources import RELATION_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(RELATION_RESOURCE)
