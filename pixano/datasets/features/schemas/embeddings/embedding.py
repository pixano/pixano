# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.python import issubclass_strict

from ...types.schema_reference import ItemRef
from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


@_register_schema_internal
class Embedding(BaseSchema):
    """Embedding Lance Model.

    Attributes:
        item_ref (ItemRef, optional): Reference to the embedding's item.
    """

    item_ref: ItemRef = ItemRef.none()

    @property
    def item(self):
        """Get the item."""
        return self.resolve_ref(self.item_ref)


def is_embedding(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Embedding or subclass of Embedding."""
    return issubclass_strict(cls, Embedding, strict)
