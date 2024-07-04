# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.python import issubclass_strict

from .base_schema import BaseSchema
from .registry import _register_schema_internal


@_register_schema_internal
class Item(BaseSchema):
    """Item Lance Model."""

    split: str


def is_item(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Item or subclass of Item."""
    return issubclass_strict(cls, Item, strict)
