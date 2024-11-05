# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class Text(View):
    """Text view.

    Attributes:
        content: The text content.
    """

    content: str


def is_text(cls: type, strict: bool = False) -> bool:
    """Check if the given class is `Text` or a subclass of `Text`."""
    return issubclass_strict(cls, Text, strict)


def create_text(
    content: str,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    parent_ref: ViewRef = ViewRef.none(),
) -> Text:
    """Create a `Text` instance.

    Args:
        content: The text content.
        id: Text ID.
        item_ref: Item reference.
        parent_ref: Parent view reference.

    Returns:
        The created `Text` instance.
    """
    return Text(id=id, item_ref=item_ref, parent_ref=parent_ref, content=content)
