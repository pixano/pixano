# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Masks router."""

from pixano.api.resources import MASK_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(MASK_RESOURCE)
