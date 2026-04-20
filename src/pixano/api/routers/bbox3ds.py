# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""BBox3Ds router."""

from pixano.api.resources import BBOX3D_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(BBOX3D_RESOURCE)
