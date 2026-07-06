# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Time series REST resource (read-only)."""

from pixano.api.resources import TIMESERIES_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(TIMESERIES_RESOURCE)
