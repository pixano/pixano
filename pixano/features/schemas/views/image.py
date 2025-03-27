# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import io
from pathlib import Path
from typing import Literal, overload
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import PIL.Image
from PIL.Image import Image as PILImage

from pixano.features.utils.image import image_to_base64
from pixano.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class Image(View):
    """Image view.

    Attributes:
        url: The image URL. Can be relative or absolute or a data URL.
        width: The image width.
        height: The image height.
        format: The image format.
    """

    url: str
    width: int
    height: int
    format: str

    @overload
    def open(self, media_dir: Path | None, output_type: Literal["base64"] = "base64") -> str: ...
    @overload
    def open(self, media_dir: Path | None, output_type: Literal["image"]) -> PILImage: ...
    def open(
        self,
        media_dir: Path | None = None,
        output_type: Literal["base64", "image"] = "base64",
    ) -> str | PILImage:
        """Open the image.

        Note:
            If the output type is "base64", the image is returned as a base64 string formatted as
            "data:image/{image_format};base64,{base64}".

        Args:
            media_dir: Path to the media directory. If the URL is relative, it is relative to this directory.
            output_type: The output type. Can be "base64" or "image" (PIL.Image).

        Returns:
            opened image.
        """
        return Image.open_url(url=self.url, media_dir=media_dir, output_type=output_type)

    @overload
    @staticmethod
    def open_url(
        url: str,
        media_dir: Path | None,
        output_type: Literal["base64"] = "base64",
    ) -> str: ...
    @overload
    @staticmethod
    def open_url(
        url: str,
        media_dir: Path | None,
        output_type: Literal["image"],
    ) -> PILImage: ...
    @staticmethod
    def open_url(
        url: str,
        media_dir: Path | None = None,
        output_type: Literal["base64", "image"] = "base64",
    ) -> str | PILImage:
        """Open an image from a URL.

        Note:
            If the output type is "base64", the image is returned as a base64 string formatted as
            "data:image/{image_format};base64,{base64}".

        Args:
            url: image url relative to media_dir or absolute.
            media_dir: path to the media directory if the URL is relative.
            output_type: output type. Can be "base64" or "image" (PIL.Image).

        Returns:
            The opened image.
        """
        if output_type not in ["base64", "image"]:
            raise ValueError(f"Invalid output type: {output_type}")

        # URI is incomplete
        if urlparse(url).scheme == "":
            if media_dir is None:
                raise ValueError("URI is incomplete, need media directory")
            uri_prefix = media_dir.absolute().as_uri()
            # URI prefix exists
            if uri_prefix is not None:
                parsed_uri = urlparse(uri_prefix)
                # URI prefix is incomplete
                if parsed_uri.scheme == "":
                    raise ValueError("URI prefix is incomplete, no scheme provided (http://, file://, ...)")
                if url.startswith("/"):
                    url = url[1:]
                combined_path = Path(parsed_uri.path) / url
                parsed_uri = parsed_uri._replace(path=str(combined_path))
                api_url = parsed_uri.geturl()
            else:
                # No URI prefix
                raise ValueError("URI is incomplete, need URI prefix")
        # URI is already complete
        else:
            api_url = url

        try:
            with urlopen(api_url) as f:
                im_bytes = f.read()
        except URLError:
            raise ValueError(f"Error: image not found ({api_url})")

        pil_image = PIL.Image.open(io.BytesIO(im_bytes))

        # Handle output types
        if output_type == "base64":
            return image_to_base64(pil_image)

        return pil_image

    def shorten_url_to_relative_path(self, url_relative_path: Path) -> str:
        """Changes the URL of an image to be relative.

        Note:
           This helps the creation of a dataset where Image object are created
           with known dimensions format and theorical path, but images are not yet accessible.

        Args:
            url_relative_path (Path): The path to convert the URL to a relative path,
                eg for images to be later searchable in the media_dir.

        Returns:
            str: shorten image url
        """
        url = Path(self.url)
        url_relative_path = Path(url_relative_path)
        self.url = url.relative_to(url_relative_path).as_posix()
        return self.url


def is_image(cls: type, strict: bool = False) -> bool:
    """Check if the given class is `Image` or a subclass of `Image`."""
    return issubclass_strict(cls, Image, strict)


def create_image(
    url: Path,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    parent_ref: ViewRef = ViewRef.none(),
    width: int | None = None,
    height: int | None = None,
    format: str | None = None,
    url_relative_path: Path | None = None,
) -> Image:
    """Create an `Image` instance.

    Args:
        url: The image URL. If not relative, the URL is converted to a relative path using `url_relative_path`.
        id: Image ID.
        item_ref: Item reference.
        parent_ref: Parent view reference.
        width: The image width. If None, the width is extracted from the image file.
        height: The image height. If None, the height is extracted from the image file.
        format: The image format. If None, the format is extracted from the image file.
        url_relative_path: The path to convert the URL to a relative path,
            eg for images to be searchable in the media_dir.

    Returns:
        The created `Image` instance.
    """
    none_conditions = [width is None, height is None, format is None]
    not_none_conditions = [width is not None, height is not None, format is not None]
    if not all(none_conditions) and not all(not_none_conditions):
        raise ValueError("width, height and format must be all defined or all None")

    url = Path(url)

    if width is None:
        img = PIL.Image.open(url)
        width = img.width
        height = img.height
        format = img.format

    if url_relative_path is not None:
        url_relative_path = Path(url_relative_path)
        url = url.relative_to(url_relative_path)

    return Image(
        id=id,
        item_ref=item_ref,
        parent_ref=parent_ref,
        url=str(url.as_posix()),
        width=width,
        height=height,
        format=format,
    )
