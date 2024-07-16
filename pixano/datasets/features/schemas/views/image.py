# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import PIL
import shortuuid

from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class Image(View):
    """Image Lance Model."""

    url: str
    width: int
    height: int
    format: str

    def open(self, media_dir: Path) -> str:
        """Open image.

        Args:
            media_dir (Path): image path

        Returns:
            str: opened image
        """
        return Image.open_url(self.url, media_dir)

    @staticmethod
    def open_url(url: str, media_dir: Path) -> str:
        """Open URL image.

        Args:
            url (str): image url
            media_dir (Path): uri prefix

        Raises:
            ValueError: No scheme provided
            ValueError: Incomplete URI

        Returns:
            str: opened image
        """
        # URI is incomplete
        if urlparse(url).scheme == "":
            uri_prefix = media_dir.absolute().as_uri()
            # URI prefix exists
            if uri_prefix is not None:
                parsed_uri = urlparse(uri_prefix)
                # URI prefix is incomplete
                if parsed_uri.scheme == "":
                    raise ValueError("URI prefix is incomplete, " "no scheme provided (http://, file://, ...)")
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
            print(f"Error: image not found ({api_url})")
            return ""

        if im_bytes is not None:
            encoded = base64.b64encode(im_bytes).decode("utf-8")
            return f"data:image;base64,{encoded}"
        return ""


def is_image(cls: type, strict: bool = False) -> bool:
    """Check if the given class is Image or a subclass of Image."""
    return issubclass_strict(cls, Image, strict)


def create_image(
    url: Path,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    parent_ref: ViewRef = ViewRef.none(),
    width: int | None = None,
    height: int | None = None,
    format: str | None = None,
    other_path: Path | None = None,
) -> Image:
    """Create an Image instance.

    Args:
        url (Path): The image URL. If not relative, the URL is converted to a relative path using `other_path`.
        id (str, optional): Image ID.
        item_ref (ItemRef, optional): Item reference.
        parent_ref (ViewRef, optional): Parent view reference.
        width (int | None, optional): The image width. If None, the width is extracted from the image file.
        height (int | None, optional): The image height. If None, the height is extracted from the image file.
        format (str | None, optional): The image format. If None, the format is extracted from the image file.
        other_path (Path | None, optional): The path to convert the URL to a relative path.

    Returns:
        Image: The created Image instance.
    """
    none_conditions = [width is None, height is None, format is None]
    not_none_conditions = [width is not None, height is not None, format is not None]
    if not all(none_conditions) and not all(not_none_conditions):
        raise ValueError("width, height and format must be all defined or all None")

    url = Path(url)
    if id is None:
        id = shortuuid.uuid()

    if width is None:
        img = PIL.Image.open(url)
        width = img.width
        height = img.height
        format = img.format

    if other_path is not None:
        other_path = Path(other_path)
        url = url.relative_to(other_path)

    return Image(
        id=id, item_ref=item_ref, parent_ref=parent_ref, url=url.as_posix(), width=width, height=height, format=format
    )
