# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

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
    id: str = "",
    content: str | None = None,
    url: str | None = None,
    item_ref: ItemRef = ItemRef.none(),
    parent_ref: ViewRef = ViewRef.none(),
    url_relative_path: Path | None = None,
) -> Text:
    """Create a `Text` instance.

    Args:
        content: The text content.
        url: The url to access the raw text content in UTF8 if not specified directly.
        id: Text ID.
        item_ref: Item reference.
        parent_ref: Parent view reference.
        url_relative_path: The path to convert the URL to a relative path.

    Returns:
        The created `Text` instance.
    """
    if (content == "" or content is None) and isinstance(url, str):
        p_url: Path = Path(url)
        content = p_url.read_text()

    return Text(id=id, item_ref=item_ref, parent_ref=parent_ref, content=content)
