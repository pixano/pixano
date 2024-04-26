# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info
import typing
from urllib.request import urlopen, URLError
from urllib.parse import urlparse
from pathlib import Path
import base64

from .registry import _register_schema_internal
from .view import View


@_register_schema_internal
class Image(View):
    """Image Lance Model."""

    url: str
    width: int
    height: int
    format: str

    def open(self, media_dir: Path) -> typing.IO:
        return Image.open_url(self.url, media_dir)

    @staticmethod
    def open_url(url, media_dir: Path) -> typing.IO:
        # URI is incomplete
        if urlparse(url).scheme == "":
            uri_prefix = media_dir.absolute().as_uri()
            # URI prefix exists
            if uri_prefix is not None:
                parsed_uri = urlparse(uri_prefix)
                # URI prefix is incomplete
                if parsed_uri.scheme == "":
                    raise ValueError(
                        "URI prefix is incomplete, no scheme provided (http://, file://, ...)"
                    )
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


def is_image(cls: typing.Any) -> bool:
    """Check if the given class is a subclass of Image.

    Args:
        cls (typing.Any): The class to check.

    Returns:
        bool: True if the class is a subclass of Image, False otherwise.
    """
    return cls is Image
