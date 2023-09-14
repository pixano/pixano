# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purcompressedRLE is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from typing import Any

import numpy as np
import pyarrow as pa
from PIL import Image
from pydantic import BaseModel, PrivateAttr

from pixano.core.pixano_type import PixanoType, create_pyarrow_type
from pixano.utils import (
    encode_rle,
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)


class CompressedRLE(PixanoType, BaseModel):
    """Compressed RLE mask type

    Attributes:
        _size (list[float]): Mask size
        _counts (bytes): Mask RLE encoding
    """

    _size: list[float] = PrivateAttr()
    _counts: bytes = PrivateAttr()

    def __init__(self, size: list[float], counts: bytes):
        """Initalize compressed RLE mask

        Args:
            size (list[float]): Mask size
            counts (bytes): Mask RLE encoding
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__()

        # Define private attributes manually
        self._size = size
        self._counts = counts

    @property
    def size(self) -> list[float]:
        """Return mask size

        Returns:
            list[float]: Mask size
        """

        return self._size

    @property
    def counts(self) -> bytes:
        """Return mask RLE encoding

        Returns:
            bytes: Mask RLE encoding
        """

        return self._counts if not None else b""

    def to_mask(self) -> np.ndarray:
        """Convert compressed RLE mask to NumPy array

        Returns:
            np.ndarray: Mask as NumPy array
        """

        return rle_to_mask(self.to_dict())

    def to_urle(self) -> dict[str, Any]:
        """Convert compressed RLE mask to uncompressed RLE

        Returns:
            dict[str, Any]: Mask as uncompressed RLE
        """

        return rle_to_urle(self.to_dict())

    def to_polygons(self) -> list[list]:
        """Convert compressed RLE mask to poylgons

        Returns:
            list[list]: Mask as polygons
        """

        return rle_to_polygons(self.to_dict())

    @staticmethod
    def from_mask(mask: Image.Image | np.ndarray) -> "CompressedRLE":
        """Create compressed RLE mask from NumPy array

        Args:
            mask (Image.Image | np.ndarray): Mask as NumPy array

        Returns:
            CompressedRLE: Compressed RLE mask
        """

        return CompressedRLE.from_dict(mask_to_rle(mask))

    @staticmethod
    def from_urle(urle: dict[str, Any]) -> "CompressedRLE":
        """Create compressed RLE mask from uncompressed RLE

        Args:
            urle (dict[str, Any]): Mask as uncompressed RLE

        Returns:
            CompressedRLE: Compressed RLE mask
        """

        return CompressedRLE.from_dict(urle_to_rle(urle))

    @staticmethod
    def from_polygons(
        polygons: list[list],
        height: int,
        width: int,
    ) -> "CompressedRLE":
        """Create compressed RLE mask from polygons

        Args:
            polygons (list[list]): Mask as polygons
            height (int): Image height
            width (int): Image width

        Returns:
            CompressedRLE: Compressed RLE mask
        """

        return CompressedRLE.from_dict(polygons_to_rle(polygons, height, width))

    @staticmethod
    def encode(
        mask: list[list] | dict[str, Any], height: int, width: int
    ) -> "CompressedRLE":
        """Create compressed RLE mask from polygons / uncompressed RLE / compressed RLE

        Args:
            mask (list[list] | dict[str, Any]): Mask as polygons / uncompressed RLE / compressed RLE
            height (int): Image height
            width (int): Image width

        Returns:
            CompressedRLE: Compressed RLE mask
        """

        return CompressedRLE.from_dict(encode_rle(mask, height, width))

    @staticmethod
    def to_struct() -> pa.StructType:
        """Return CompressedRLE type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        return pa.struct(
            [
                pa.field("size", pa.list_(pa.int32(), list_size=2)),
                pa.field("counts", pa.binary()),
            ]
        )


CompressedRLEType = create_pyarrow_type(
    CompressedRLE.to_struct(), "CompressedRLE", CompressedRLE
)
