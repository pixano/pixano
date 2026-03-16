# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Messages router."""

from pixano.api.resources import MESSAGE_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(MESSAGE_RESOURCE)
