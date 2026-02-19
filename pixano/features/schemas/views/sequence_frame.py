# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pathlib import Path

from pixano.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .image import Image, create_image


@_register_schema_internal
class SequenceFrame(Image):
    """Sequence Frame view.

    Attributes:
        timestamp: The timestamp of the frame.
        frame_index: The index of the frame in the sequence.
    """

    timestamp: float
    frame_index: int


def is_sequence_frame(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `SequenceFrame`."""
    return issubclass_strict(cls, SequenceFrame, strict)


def create_sequence_frame(
    url: Path | str = "",
    timestamp: float = 0.0,
    frame_index: int = 0,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    parent_ref: ViewRef = ViewRef.none(),
    width: int | None = None,
    height: int | None = None,
    format: str | None = None,
    url_relative_path: Path | None = None,
    blob: bytes | None = None,
) -> SequenceFrame:
    """Create a `SequenceFrame` instance.

    Args:
        url: The frame URL. If not relative, the URL is converted to a relative path using `other_path`.
            Can be empty when using embedded blob.
        timestamp: The timestamp of the frame.
        frame_index: The index of the frame in the sequence.
        id: Frame ID.
        item_ref: Item reference.
        parent_ref: Parent view reference.
        width: The frame width. If None, the width is extracted from the frame file or blob.
        height: The frame height. If None, the height is extracted from the frame file or blob.
        format: The frame format. If None, the format is extracted from the frame file or blob.
        url_relative_path: The path to convert the URL to a relative path.
        blob: Raw frame bytes. When provided and width/height/format are None, they are extracted from the blob.

    Returns:
        The created `SequenceFrame` instance.
    """
    image = create_image(url, id, item_ref, parent_ref, width, height, format, url_relative_path, blob)
    return SequenceFrame(
        id=id,
        item_ref=item_ref,
        parent_ref=parent_ref,
        url=image.url,
        width=image.width,
        height=image.height,
        format=image.format,
        blob=image.blob,
        timestamp=timestamp,
        frame_index=frame_index,
    )
