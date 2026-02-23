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
class View(BaseSchema):
    """View base class.

    Views are used to define a view in a dataset such as an image, a point cloud, a text. It can refer to an item and
    a parent view.

    Attributes:
        item_id: ID of the view's item.
        parent_id: ID of the view's parent view.
        view_name: Logical view name (sensor/modality identifier).
    """

    item_id: str = ""
    parent_id: str = ""
    view_name: str = ""

    @property
    def item(self) -> "Item":
        """Get the view's item."""
        if self.item_id == "":
            raise ValueError("item_id is not set.")
        return self.dataset.get_data("item", ids=[self.item_id])[0]

    @property
    def parent(self) -> "View":
        """Get the view's parent view."""
        if self.parent_id == "":
            raise ValueError("parent_id is not set.")
        # Parent can be any view table; search by id across view tables.
        for group, tables in self.dataset.schema.groups.items():
            if getattr(group, "value", "") != "views":
                continue
            for table_name in tables:
                parent = self.dataset.get_data(table_name, ids=self.parent_id)
                if parent is not None:
                    return parent
        raise ValueError(f"Parent view '{self.parent_id}' not found.")


def is_view(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `View` or subclass of `View`."""
    return issubclass_strict(cls, View, strict)
