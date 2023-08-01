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

from typing import Optional

import pyarrow as pa
from numpy import ndarray
from PIL import Image
from pydantic import BaseModel, PrivateAttr

from .pixano_type import PixanoType, createPaType
from pixano.transforms.image import (
    encode_rle,
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)

# ------------------------------------------------
#             Python type
# ------------------------------------------------


class CompressedRLE(PixanoType, BaseModel):
    _size: list[float] = PrivateAttr()
    _counts: Optional[bytes] = PrivateAttr()

    def __init__(self, size: list[float], counts: bytes):
        # Define public attributes through Pydantic BaseModel
        super().__init__()

        # Define private attributes manually
        self._size = size
        self._counts = counts

    @property
    def size(self) -> list[float]:
        return self._size

    @property
    def counts(self) -> bytes:
        return self._counts if not None else b""

    def to_mask(self) -> ndarray:
        return rle_to_mask(self.to_dict())

    def to_urle(self) -> dict:
        return rle_to_urle(self.to_dict())

    def to_polygons(self) -> list[list]:
        return rle_to_polygons(self.to_dict())

    @staticmethod
    def from_mask(mask: Image.Image | ndarray) -> "CompressedRLE":
        rle_dict = mask_to_rle(mask)
        return CompressedRLE.from_dict(rle_dict)

    @staticmethod
    def from_urle(urle: list[int]) -> "CompressedRLE":
        rle_dict = urle_to_rle(urle)
        return CompressedRLE.from_dict(rle_dict)

    @staticmethod
    def from_polygons(
        polygons: list[float], height: int, width: int
    ) -> "CompressedRLE":
        rle_dict = polygons_to_rle(polygons, height, width)
        return CompressedRLE.from_dict(rle_dict)

    @staticmethod
    def encode(mask: list[list] | dict, height: int, width: int):
        return CompressedRLE.from_dict(encode_rle(mask, height, width))

    @classmethod
    def to_struct(cls):
        return pa.struct(
            [
                pa.field("size", pa.list_(pa.int32(), list_size=2)),
                pa.field("counts", pa.binary()),
            ]
        )


CompressedRLEType = createPaType(
    CompressedRLE.to_struct(), "CompressedRLE", CompressedRLE
)
