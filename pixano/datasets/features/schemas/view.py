# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.python import issubclass_strict

from .base_schema import BaseSchema
from .registry import _register_schema_internal


@_register_schema_internal
class View(BaseSchema):
    """View Lance Model."""

    item_id: str


def is_view(cls: type, strict: bool = False) -> bool:
    """Check if a class is an View or subclass of View."""
    return issubclass_strict(cls, View, strict)
