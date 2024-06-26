# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .base_schema import BaseSchema
from .registry import _register_schema_internal


@_register_schema_internal
class Item(BaseSchema):
    """Item Lance Model."""

    split: str
