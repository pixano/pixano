# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing_extensions import TYPE_CHECKING

from pixano.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


if TYPE_CHECKING:
    from pixano.features.schemas import Item


@_register_schema_internal
class View(BaseSchema):
    """View base class.

    Views are used to define a view in a dataset such as an image, a point cloud, a text. It can refer to an item and
    a parent view.

    Attributes:
        item_ref: Reference to the view's item.
        parent_ref: Reference to the view's parent view.
    """

    item_ref: ItemRef = ItemRef.none()
    parent_ref: ViewRef = ViewRef.none()

    @property
    def item(self) -> "Item":
        """Get the view's item."""
        return self.resolve_ref(self.item_ref)

    @property
    def parent(self) -> "View":
        """Get the view's parent view."""
        return self.resolve_ref(self.parent_ref)


def is_view(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `View` or subclass of `View`."""
    return issubclass_strict(cls, View, strict)
