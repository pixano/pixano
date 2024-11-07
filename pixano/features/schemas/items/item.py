# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


@_register_schema_internal
class Item(BaseSchema):
    """Item base class.

    Items are used to store information about an item in a dataset. It contains at least a split attribute.
    It also federates the information about the item's views, entities, annotations, embeddings, etc via its id.

    Attributes:
        split: Split of the item.
    """

    split: str = "default"


def is_item(cls: type, strict: bool = False) -> bool:
    """Check if a class is an `Item` or subclass of `Item`."""
    return issubclass_strict(cls, Item, strict)
