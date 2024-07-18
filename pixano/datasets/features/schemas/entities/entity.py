# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


@_register_schema_internal
class Entity(BaseSchema):
    """Object Lance Model."""

    item_ref: ItemRef = ItemRef.none()
    view_ref: ViewRef = ViewRef.none()
    parent_ref: EntityRef = EntityRef.none()

    @property
    def item(self):
        """Get the item."""
        return self.resolve_ref(self.item_ref)

    @property
    def view(self):
        """Get the view."""
        return self.resolve_ref(self.view_ref)

    @property
    def parent(self):
        """Get the parent."""
        return self.resolve_ref(self.parent_ref)


def is_entity(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Entity or subclass of Entity."""
    return issubclass_strict(cls, Entity, strict)
