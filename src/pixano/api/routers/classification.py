# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Classifications router."""

from pixano.api.resources import CLASSIFICATION_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(CLASSIFICATION_RESOURCE)
