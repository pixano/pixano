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
from PIL.Image import Image as PILImage

from pixano.features.utils.image import image_to_base64
from pixano.utils import issubclass_strict

from .view import View


def _generate_preview(pil_image: PILImage) -> bytes:
    """Generate a 64x64 PNG thumbnail from a PIL image.

    Args:
        pil_image: Source PIL image (not modified in-place).

    Returns:
        PNG-encoded thumbnail bytes.
    """
    thumb = pil_image.copy()
    thumb.thumbnail((64, 64))
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    return buf.getvalue()


class Image(View):
    """Image record modality.

    Attributes:
        width: The image width.
        height: The image height.
        format: The image format.
    """

    width: int = 0
    height: int = 0
    format: str = ""

    def open(
        self,
        *,
        as_base64: bool = False,
    ) -> str | PILImage:
        """Open the image.

        Note:
            If `as_base64` is True, the image is returned as a base64 string formatted as
            "data:image/{image_format};base64,{base64}".

        Args:
            as_base64: Whether to return the opened image as a base64 data URI instead of a PIL image.

        Returns:
            The opened image as a `PIL.Image.Image`, or a base64 data URI string when `as_base64` is True.
        """
        if self.raw_bytes and len(self.raw_bytes) > 0:
            pil_image = PIL.Image.open(io.BytesIO(self.raw_bytes))

        elif self.uri and urlparse(self.uri).scheme != "":
            pil_image = Image.open_url(url=self.uri)

        if as_base64:
            return image_to_base64(pil_image)
        return pil_image

    @classmethod
    def from_uri(
        cls,
        record_id: str,
        logical_name: str,
        uri: str,
        *,
        id: str | None = None,
    ) -> Image:
        """Create an ``Image`` from a URI (local path or remote URL).

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            uri: Absolute file path or remote ``http(s)`` URL.
            id: Optional explicit ID.  Auto-generated when `None`.

        Returns:
            A fully-populated ``Image`` instance.
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
        )

    @classmethod
    def from_bytes(
        cls,
        record_id: str,
        logical_name: str,
        raw_bytes: bytes,
        *,
        id: str | None = None,
    ) -> Image:
        """Create an ``Image`` from raw bytes.

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            raw_bytes: Image file content as raw bytes.
            id: Optional explicit ID.  Auto-generated when `None`.

        Returns:
            A fully-populated ``Image`` instance.
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
        )


def is_image(cls: type, strict: bool = False) -> bool:
    """Check if the given class is ``Image`` or a subclass of ``Image``."""
    return issubclass_strict(cls, Image, strict)
