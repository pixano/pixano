# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
import io
from pathlib import Path
from urllib.parse import urlparse

import PIL.Image
from PIL.Image import Image as PILImage

from pixano.features.utils.image import image_to_base64
from pixano.utils import issubclass_strict

from .view import View


class Image(View):
    """Image record modality.

    Attributes:
        uri: The image URI. Can be relative or absolute or a data URI. Empty when embedded.
        width: The image width.
        height: The image height.
        format: The image format.
        raw_bytes: Raw image bytes. Empty when using URI.
    """

    uri: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    raw_bytes: bytes = b""

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


def is_image(cls: type, strict: bool = False) -> bool:
    """Check if the given class is `Image` or a subclass of `Image`."""
    return issubclass_strict(cls, Image, strict)


def create_image(
    id: str,
    record_id: str,
    logical_name: str,
    width: int | None = None,
    height: int | None = None,
    format: str | None = None,
    uri: str | None = None,
    raw_bytes: bytes | None = None,
) -> Image:
    """Create an `Image` instance.

    Args:
        id: Image ID.
        record_id: Record ID.
        logical_name: Logical view name (e.g. "front_camera").
        width: The image width. If None, the width is extracted from the image file or bytes.
        height: The image height. If None, the height is extracted from the image file or bytes.
        format: The image format. If None, the format is extracted from the image file or bytes.
        uri: The image URI.
        raw_bytes: Raw image bytes. When provided and width/height/format are None, they are extracted from the bytes.

    Returns:
        The created `Image` instance.
    """
    none_conditions = [width is None, height is None, format is None]
    not_none_conditions = [width is not None, height is not None, format is not None]
    if not all(none_conditions) and not all(not_none_conditions):
        raise ValueError("width, height and format must be all defined or all None")
    if raw_bytes is not None and len(raw_bytes) > 0 and width is None:
        img = PIL.Image.open(io.BytesIO(raw_bytes))
        width = img.width
        height = img.height
        format = img.format
        return Image(
            id=id,
            record_id=record_id,
            logical_name=logical_name,
            uri="",
            width=width,
            height=height,
            format=format,
            raw_bytes=raw_bytes,
        )
    if width is None:
        img = PIL.Image.open(io.BytesIO(raw_bytes))
        width = img.width
        height = img.height
        format = img.format

    return Image(
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        uri=uri,
        width=width,
        height=height,
        format=format,
        raw_bytes=raw_bytes or b"",
    )
