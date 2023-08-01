# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from pathlib import Path
from typing import IO, Optional
from urllib.parse import urlparse
from urllib.request import urlopen

import cv2
import numpy as np
import pyarrow as pa
from IPython.core.display import Image as IPyImage
from PIL import Image as PILImage
from pydantic import BaseModel, PrivateAttr

from .pixano_type import PixanoType, createPaType
from pixano.utils.image import binary_to_url

# ------------------------------------------------
#             Python type
# ------------------------------------------------


class Image(PixanoType, BaseModel):
    """Image type using URI or bytes

    Attributes:
        _uri (str): Image URI
        _bytes (bytes): Image bytes
        _preview_bytes (bytes): Image preview bytes
        uri_prefix (str): URI prefix for relative URIs
    """

    _uri: str = PrivateAttr()
    _bytes: Optional[bytes] = PrivateAttr()
    _preview_bytes: Optional[bytes] = PrivateAttr()
    uri_prefix: Optional[str]

    def __init__(
        self,
        uri: str,
        bytes: bytes = None,
        preview_bytes: bytes = None,
        uri_prefix: str = None,
    ):
        """Initialize image from URI or bytes

        Attributes:
            uri (str): Image URI
            bytes (bytes, optional): Image bytes. Defaults to None.
            preview_bytes (bytes, optional): Image preview bytes. Defaults to None.
            uri_prefix (str, optional): URI prefix for relative URIs. Defaults to None.
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__(uri_prefix=uri_prefix)

        # Define private attributes manually
        self._uri = uri
        self._bytes = bytes
        self._preview_bytes = preview_bytes

    @property
    def bytes(self) -> bytes:
        """Return image bytes

        Returns:
            bytes: Image bytes
        """

        if self._bytes is not None:
            return self._bytes
        elif self._uri is not None:
            with self.open() as f:
                return f.read()
        else:
            return None

    @property
    def preview_bytes(self) -> bytes:
        """Return image preview bytes

        Returns:
            bytes: Image bytes
        """

        return self._preview_bytes

    @property
    def url(self) -> str:
        """Return image URL

        Returns:
            str: Image URL
        """

        return binary_to_url(self.bytes)

    @property
    def preview_url(self) -> str:
        """Return image preview URL

        Returns:
            str: Image preview URL
        """

        return binary_to_url(self._preview_bytes)

    @property
    def uri(self) -> str:
        """Return image URI

        Returns:
            str: Image URI
        """

        # Relative URI
        if urlparse(self._uri).scheme == "":
            # If URI prefix exists
            if self.uri_prefix is not None:
                parsed_uri = urlparse(self.uri_prefix)
                if parsed_uri.scheme == "":
                    raise Exception(
                        "URI prefix is incomplete, no scheme provided (http://, file://, ...)"
                    )
                combined_path = Path(parsed_uri.path) / self._uri
                parsed_uri = parsed_uri._replace(path=str(combined_path))
                return parsed_uri.geturl()
            # No URI prefix
            else:
                return self._uri
        # Complete URI
        else:
            return self._uri

    @property
    def size(self) -> list[int]:
        """Return image size

        Returns:
            list[int]: Image size
        """
        return self.as_pillow().size

    def open(self) -> IO:
        """Open image

        Returns:
            IO: Opened image
        """

        return urlopen(self.uri)

    def as_pillow(self) -> PILImage.Image:
        """Open image as Pillow

        Returns:
            PIL.Image.Image: Image as Pillow
        """

        return PILImage.open(self.open()).convert("RGB")

    def as_cv2(self) -> np.ndarray:
        """Open image as OpenCV

        Returns:
            np.ndarray: Image as OpenCV
        """

        im_arr = np.frombuffer(self.open().read(), dtype=np.uint8)
        return cv2.imdecode(im_arr, cv2.IMREAD_COLOR)

    def display(self, preview=False) -> IPyImage:
        """Display image

        Args:
            preview (bool, optional): True to display image preview instead of full image. Defaults to False.

        Returns:
            IPython.core.display.Image: Image as IPython Display
        """

        im_bytes = self._preview_bytes if preview else self.bytes
        return IPyImage(url=binary_to_url(im_bytes), format=IPyImage(im_bytes).format)

    @classmethod
    def to_struct(cls) -> pa.StructType:
        return pa.struct(
            [
                pa.field("uri", pa.utf8()),
                pa.field("bytes", pa.binary()),
                pa.field("preview_bytes", pa.binary()),
            ]
        )


ImageType = createPaType(Image.to_struct(), "Image", Image)
