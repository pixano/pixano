# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from .view import View


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
    record_id: str = "",
    logical_name: str = "",
    uri: str = "",
) -> Text:
    """Create a `Text` instance.

    Args:
        content: The text content.
        id: Text ID.
        record_id: Record ID.
        logical_name: Logical view name (e.g. "text").
        uri: URI for text loaded from a file.

    Returns:
        The created `Text` instance.
    """
    return Text(
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        content=content,
        uri=uri,
    )
