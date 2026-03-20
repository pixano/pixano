# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Embeddings router."""

from pixano.api.resources import EMBEDDING_RESOURCE
from pixano.api.routers.resources import create_resource_router


router = create_resource_router(EMBEDDING_RESOURCE)
