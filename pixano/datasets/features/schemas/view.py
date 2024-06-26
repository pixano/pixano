# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .base_schema import BaseSchema
from .registry import _register_schema_internal


@_register_schema_internal
class View(BaseSchema):
    """View Lance Model."""

    item_id: str
