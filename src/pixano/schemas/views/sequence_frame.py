# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import io
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import PIL.Image
import shortuuid

from pixano.utils import issubclass_strict

from .image import Image, _generate_preview


class SequenceFrame(Image):
    """Sequence of image. Used to store video frames.

    Attributes:
        timestamp: The timestamp of the frame.
        frame_index: The index of the frame in the sequence.
    """

    timestamp: float
    frame_index: int

    @classmethod
    def from_uri(  # type: ignore[override]
        cls,
        record_id: str,
        logical_name: str,
        uri: str,
        timestamp: float,
        frame_index: int,
        *,
        id: str | None = None,
    ) -> SequenceFrame:
        """Create a ``SequenceFrame`` from a URI (local path or remote URL).

        The file is opened to extract *width*, *height* and *format*, and a
        64 x 64 PNG preview thumbnail is generated automatically.

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            uri: Absolute file path or remote ``http(s)`` URL.
            timestamp: The timestamp of the frame.
            frame_index: The index of the frame in the sequence.
            id: Optional explicit ID.  Auto-generated with :func:`shortuuid.uuid`
                when *None*.

        Returns:
            A fully-populated ``SequenceFrame`` instance.
        """
        if id is None:
            id = shortuuid.uuid()

        parsed = urlparse(uri)
        if parsed.scheme in ("http", "https"):
            data = urlopen(uri).read()  # noqa: S310
            pil_image = PIL.Image.open(io.BytesIO(data))
        else:
            pil_image = PIL.Image.open(Path(uri))

        width = pil_image.width
        height = pil_image.height
        fmt = pil_image.format or ""
        preview = _generate_preview(pil_image)

        return cls(
            id=id,
            record_id=record_id,
            logical_name=logical_name,
            uri=uri,
            width=width,
            height=height,
            format=fmt,
            preview=preview,
            preview_format="png",
            timestamp=timestamp,
            frame_index=frame_index,
        )

    @classmethod
    def from_bytes(  # type: ignore[override]
        cls,
        record_id: str,
        logical_name: str,
        raw_bytes: bytes,
        timestamp: float,
        frame_index: int,
        *,
        id: str | None = None,
    ) -> SequenceFrame:
        """Create a ``SequenceFrame`` from raw bytes.

        The bytes are decoded to extract *width*, *height* and *format*, and a
        64 x 64 PNG preview thumbnail is generated automatically.

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            raw_bytes: Image file content as raw bytes.
            timestamp: The timestamp of the frame.
            frame_index: The index of the frame in the sequence.
            id: Optional explicit ID.  Auto-generated with :func:`shortuuid.uuid`
                when *None*.

        Returns:
            A fully-populated ``SequenceFrame`` instance.
        """
        if id is None:
            id = shortuuid.uuid()

        pil_image = PIL.Image.open(io.BytesIO(raw_bytes))

        width = pil_image.width
        height = pil_image.height
        fmt = pil_image.format or ""
        preview = _generate_preview(pil_image)

        return cls(
            id=id,
            record_id=record_id,
            logical_name=logical_name,
            raw_bytes=raw_bytes,
            width=width,
            height=height,
            format=fmt,
            preview=preview,
            preview_format="png",
            timestamp=timestamp,
            frame_index=frame_index,
        )


def is_sequence_frame(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of ``SequenceFrame``."""
    return issubclass_strict(cls, SequenceFrame, strict)
