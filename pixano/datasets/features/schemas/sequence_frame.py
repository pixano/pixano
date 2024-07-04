# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pathlib import Path

from pixano.datasets.utils import issubclass_strict

from .image import Image, create_image
from .registry import _register_schema_internal


@_register_schema_internal
class SequenceFrame(Image):
    """Sequence Frame Lance Model."""

    sequence_id: str
    timestamp: float
    frame_index: int


def is_sequence_frame(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of Sequence."""
    return issubclass_strict(cls, SequenceFrame, strict)


def create_sequence_frame(
    item_id: str,
    sequence_id: str,
    url: Path,
    timestamp: float,
    frame_index: int,
    id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    format: str | None = None,
    other_path: Path | None = None,
) -> SequenceFrame:
    """Create a SequenceFrame instance.

    Args:
        item_id (str): The item id.
        sequence_id (str): The sequence id.
        url (Path): The frame URL. If not relative, the URL is converted to a relative path using `other_path`.
        timestamp (float): The timestamp of the frame.
        frame_index (int): The index of the frame in the sequence.
        id (str | None, optional): The frame id. If None, a random id is generated.
        width (int | None, optional): The frame width. If None, the width is extracted from the frame file.
        height (int | None, optional): The frame height. If None, the height is extracted from the frame file.
        format (str | None, optional): The frame format. If None, the format is extracted from the frame file.
        other_path (Path | None, optional): The path to convert the URL to a relative path.

    Returns:
        Image: The created Image instance.
    """
    image = create_image(item_id, url, id, width, height, format, other_path)
    return SequenceFrame(
        id=image.id,
        item_id=item_id,
        sequence_id=sequence_id,
        url=image.url,
        width=image.width,
        height=image.height,
        format=image.format,
        timestamp=timestamp,
        frame_index=frame_index,
    )
