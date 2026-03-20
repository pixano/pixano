# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Text spans router."""

from pixano.api.resources import TEXT_SPAN_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(TEXT_SPAN_RESOURCE)
