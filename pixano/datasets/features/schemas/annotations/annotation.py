# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.python import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


@_register_schema_internal
class Annotation(BaseSchema):
    """Annotation Lance Model.

    Attributes:
        item_ref (ItemRef, optional): Reference to the annotation's item.
        view_ref (ViewRef, optional): Reference to the annotation's view.
        entity_ref (EntityReference, optional): Reference to the annotation's entity.
    """

    item_ref: ItemRef = ItemRef.none()
    view_ref: ViewRef = ViewRef.none()
    entity_ref: EntityRef = EntityRef.none()


def is_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Annotation or subclass of Annotation."""
    return issubclass_strict(cls, Annotation, strict)
