# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .base_schema import BaseSchema
from .registry import _register_schema_internal


@_register_schema_internal
class Embedding(BaseSchema):
    """Embedding Lance Model."""

    id: str
    item_id: str
