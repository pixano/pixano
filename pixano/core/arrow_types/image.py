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

import base64
from typing import IO

import pyarrow as pa
from etils import epath


class Image:
    """Image type using URI string or bytes"""

    def __init__(
        self,
        uri: str,
        bytes: bytes,
        preview_bytes: bytes,
        uri_prefix: epath.PathLike = None,
    ):
        """Creates image from UIR, bytes and preview

        Attributes:
            uri (str): Image URI
            bytes (bytes): Image bytes
            preview_bytes (bytes): Image preview bytes
            uri_prefix (epath.PathLike, optional): Image URI prefix. Defaults to None.
        """
        self._uri = uri
        self._bytes = bytes
        self._preview_bytes = preview_bytes

        self.uri_prefix = uri_prefix

    @property
    def bytes(self) -> bytes:
        if self._bytes is not None:
            return self._bytes
        elif self._uri is not None:
            print(f"loading {self._uri}")
            with self.open() as f:
                return f.read()
        else:
            return None

    @property
    def preview_url(self) -> str:
        encoded = base64.b64encode(self._preview_bytes).decode("utf-8")
        url = f"data:image;base64,{encoded}"
        return url

    @property
    def url(self) -> str:
        # TODO need to check if not None
        data = self.bytes
        if data is not None:
            encoded = base64.b64encode(data).decode("utf-8")
            url = f"data:image;base64,{encoded}"
            return url
        else:
            return ""

    # TODO add prefix/auth/http/s3 ...
    def open(self) -> IO:
        if self.uri_prefix is not None:
            uri = self.uri_prefix / self._uri  # type: ignore
        else:
            uri = self._uri
        return open(uri, "rb")

    def display(self, preview=False):
        from IPython.core.display import Image as IPyImage

        if preview:
            data = self._preview_bytes
        else:
            data = self._bytes

        inferred_format = IPyImage(data).format
        encoded = base64.b64encode(data).decode("utf-8")
        url = f"data:image;base64,{encoded}"
        return IPyImage(url=url, format=inferred_format)


class ImageType(pa.ExtensionType):
    """Externalized image type containing the URI string in UTF-8"""

    def __init__(self):
        super(ImageType, self).__init__(
            pa.struct(
                [
                    pa.field("uri", pa.utf8()),
                    pa.field("bytes", pa.binary()),
                    pa.field("preview_bytes", pa.binary()),
                ]
            ),
            "Image",
        )

    def __arrow_ext_serialize__(self):
        return b""

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return ImageType()

    def __arrow_ext_scalar_class__(self):
        return ImageScalar


class ImageScalar(pa.ExtensionScalar):
    def as_py(self) -> Image:
        return Image(
            self.value["uri"].as_py(),
            self.value["bytes"].as_py(),
            self.value["preview_bytes"].as_py(),
        )


class CompressedRLEType(pa.ExtensionType):
    """Segmentation mask type as PyArrow StructType"""

    def __init__(self):
        super(CompressedRLEType, self).__init__(
            pa.struct(
                [
                    pa.field("size", pa.list_(pa.int32())),
                    pa.field("counts", pa.binary()),
                ]
            ),
            "mask[rle]",
        )

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return CompressedRLEType()

    def __arrow_ext_serialize__(self):
        return b""


def is_image_type(t: pa.DataType) -> bool:
    """Returns True if value is an instance of ImageType

    Args:
        t (pa.DataType): Value to check

    Returns:
        bool: Type checking response
    """
    return isinstance(t, ImageType)
