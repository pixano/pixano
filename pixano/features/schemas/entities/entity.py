# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing_extensions import TYPE_CHECKING

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


if TYPE_CHECKING:
    from pixano.features.schemas import Item, View


@_register_schema_internal
class Entity(BaseSchema):
    """`Entity` base class.

    Entities are used to define an entity in a dataset such as an object, a track. It can refer to an item, a view,
    and a parent entity.

    Attributes:
        item_ref: Reference to the entity's item.
        view_ref: Reference to the entity's view.
        parent_ref: Reference to the entity's parent entity.
    """

    item_ref: ItemRef = ItemRef.none()
    view_ref: ViewRef = ViewRef.none()
    parent_ref: EntityRef = EntityRef.none()

    @property
    def item(self) -> "Item":
        """Get the entity's item."""
        return self.resolve_ref(self.item_ref)

    @property
    def view(self) -> "View":
        """Get the entity's view."""
        return self.resolve_ref(self.view_ref)

    @property
    def parent(self) -> "Entity":
        """Get the entity's parent entity."""
        return self.resolve_ref(self.parent_ref)


def is_entity(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Entity or subclass of Entity."""
    return issubclass_strict(cls, Entity, strict)
