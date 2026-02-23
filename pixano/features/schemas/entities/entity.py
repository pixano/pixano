# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing_extensions import TYPE_CHECKING

from pixano.utils import issubclass_strict

from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


if TYPE_CHECKING:
    from pixano.features.schemas import Item


@_register_schema_internal
class Entity(BaseSchema):
    """`Entity` base class.

    Entities are used to define an entity in a dataset such as an object, a track. It can refer to an item, a view,
    and a parent entity.

    Attributes:
        item_id: ID of the parent item.
        parent_id: ID of the parent entity.
    """

    item_id: str = ""
    parent_id: str = ""

    @property
    def item(self) -> "Item":
        """Get the entity's item."""
        if self.item_id == "":
            raise ValueError("item_id is not set.")
        return self.dataset.get_data("item", ids=[self.item_id])[0]

    @property
    def parent(self) -> "Entity":
        """Get the entity's parent entity."""
        if self.parent_id == "":
            raise ValueError("parent_id is not set.")
        # Parent entity can be in any entity table.
        for group, tables in self.dataset.schema.groups.items():
            if getattr(group, "value", "") != "entities":
                continue
            for table_name in tables:
                parent = self.dataset.get_data(table_name, ids=self.parent_id)
                if parent is not None:
                    return parent
        raise ValueError(f"Parent entity '{self.parent_id}' not found.")


def is_entity(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Entity or subclass of Entity."""
    return issubclass_strict(cls, Entity, strict)
