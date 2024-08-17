# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils.python import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


@_register_schema_internal
class Annotation(BaseSchema):
    """Annotations are used to annotate an entity in a dataset.

    It can refer to an entity, an item, and a view.

    Attributes:
        item_ref: Reference to the annotation's item.
        view_ref: Reference to the annotation's view.
        entity_ref: Reference to the annotation's entity.
    """

    item_ref: ItemRef = ItemRef.none()
    view_ref: ViewRef = ViewRef.none()
    entity_ref: EntityRef = EntityRef.none()

    @property
    def item(self):
        """Get the item."""
        return self.resolve_ref(self.item_ref)

    @property
    def view(self):
        """Get the view."""
        return self.resolve_ref(self.view_ref)

    @property
    def entity(self):
        """Get the entity."""
        return self.resolve_ref(self.entity_ref)


def is_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Annotation or subclass of Annotation."""
    return issubclass_strict(cls, Annotation, strict)
