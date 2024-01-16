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
from pydantic import BaseModel
from s3path import S3Path

from pixano.core.pixano_type import PixanoType, create_pyarrow_type
from pixano.utils import binary_to_url

# Disable warning for Image "bytes" attribute
# NOTE: Rename attribute? Breaking change for Pixano datasets using Image
# pylint: disable=redefined-builtin, used-before-assignment


class Image(PixanoType, BaseModel):
    """Image type using URI or bytes

    Attributes:
        uri (str): Image URI
        bytes (bytes): Image bytes
        preview_bytes (bytes): Image preview bytes
        uri_prefix (str): URI prefix for relative URIs
    """

    uri: str
    bytes: Optional[bytes]
    preview_bytes: Optional[bytes]
    uri_prefix: Optional[str]

    def __init__(
        self,
        uri: str,
        bytes: bytes = None,
        preview_bytes: bytes = None,
        uri_prefix: str = None,
    ):
        """Initialize Image

        Attributes:
            uri (str): Image URI
            bytes (bytes, optional): Image bytes. Defaults to None.
            preview_bytes (bytes, optional): Image preview bytes. Defaults to None.
            uri_prefix (str, optional): URI prefix for relative URIs. Defaults to None.
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__(
            uri=uri,
            bytes=bytes,
            preview_bytes=preview_bytes,
            uri_prefix=uri_prefix,
        )

    @property
    def complete_uri(self) -> str:
        """Return complete image URI using URI and URI prefix

        Returns:
            str: Image URI
        """

        # URI is incomplete
        if urlparse(self.uri).scheme == "":
            # URI prefix exists
            if self.uri_prefix is not None:
                parsed_uri = urlparse(self.uri_prefix)
                # URI prefix is incomplete
                if parsed_uri.scheme == "":
                    raise ValueError(
                        "URI prefix is incomplete, no scheme provided (http://, file://, ...)"
                    )
                combined_path = Path(parsed_uri.path) / self.uri
                parsed_uri = parsed_uri._replace(path=str(combined_path))
                return parsed_uri.geturl()
            # No URI prefix
            raise ValueError("URI is incomplete, need URI prefix")
        # URI is already complete
        return self.uri

    @property
    def url(self) -> str:
        """Return image base 64 URL

        Returns:
            str: Image base 64 URL
        """

        return binary_to_url(self.get_bytes())

    @property
    def preview_url(self) -> str:
        """Return image preview base 64 URL

        Returns:
            str: Image preview base 64 URL
        """

        return binary_to_url(self.preview_bytes)

    @property
    def file_name(self) -> str:
        """Return image file name from URI

        Returns:
            str: Image file name
        """

        return Path(urlparse(self.uri).path).name

    @property
    def size(self) -> list[int]:
        """Return image size

        Returns:
            list[int]: Image size
        """

        return self.as_pillow().size

    @property
    def width(self) -> int:
        """Return image width

        Returns:
            int: Image width
        """

        return self.as_pillow().width

    @property
    def height(self) -> int:
        """Return image height

        Returns:
            int: Image height
        """

        return self.as_pillow().height

    def get_bytes(self) -> bytes:
        """Get image bytes from attribute or from reading file from URI

        Returns:
            bytes: Image bytes
        """

        if self.bytes is not None:
            return self.bytes
        if self.uri is not None:
            with self.open() as f:
                return f.read()
        return None

    def open(self) -> IO:
        """Open image

        Returns:
            IO: Opened image
        """

        complete_uri = self.complete_uri
        if urlparse(complete_uri).scheme == "s3":
            presigned_url = S3Path.from_uri(complete_uri).get_presigned_url()
            return urlopen(presigned_url)
        return urlopen(complete_uri)

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

        im_bytes = self.preview_bytes if preview else self.get_bytes()
        return IPyImage(url=binary_to_url(im_bytes), format=IPyImage(im_bytes).format)

    @staticmethod
    def to_struct() -> pa.StructType:
        """Return Image type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        return pa.struct(
            [
                pa.field("uri", pa.utf8()),
                pa.field("bytes", pa.binary()),
                pa.field("preview_bytes", pa.binary()),
            ]
        )


ImageType = create_pyarrow_type(Image.to_struct(), "Image", Image)
