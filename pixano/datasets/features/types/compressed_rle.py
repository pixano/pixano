# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2024)
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

import numpy as np
import pydantic
from PIL import Image as pil_image

from ...utils import image as image_utils
from .registry import _register_type_internal


@_register_type_internal
class CompressedRLE(pydantic.BaseModel):
    """Compressed RLE mask type.

    Attributes:
        size (list[int]): Mask size
        counts (bytes): Mask RLE encoding
    """

    size: list[int]
    counts: bytes

    @staticmethod
    def none():
        return CompressedRLE(size=[0, 0], counts=b'')

    def to_mask(self) -> np.ndarray:
        """Convert compressed RLE mask to NumPy array.

        Returns:
            np.ndarray: Mask as NumPy array
        """
        return image_utils.rle_to_mask(self.to_dict())

    def to_urle(self) -> dict[str, list[int]]:
        """Convert compressed RLE mask to uncompressed RLE.

        Returns:
            dict[str, list[int]]: Mask as uncompressed RLE
        """
        return image_utils.rle_to_urle(self.to_dict())

    def to_polygons(self) -> list[list]:
        """Convert compressed RLE mask to poylgons.

        Returns:
            list[list]: Mask as polygons
        """
        return image_utils.rle_to_polygons(self.to_dict())

    @staticmethod
    def from_mask(mask: pil_image.Image | np.ndarray) -> "CompressedRLE":
        """Create compressed RLE mask from NumPy array.

        Args:
            mask (Image.Image | np.ndarray): Mask as NumPy array

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        return CompressedRLE.from_dict(image_utils.mask_to_rle(mask))

    @staticmethod
    def from_urle(urle: dict[str, list[int]]) -> "CompressedRLE":
        """Create compressed RLE mask from uncompressed RLE.

        Args:
            urle (dict[str, list[int]]): Mask as uncompressed RLE

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        return CompressedRLE.from_dict(image_utils.urle_to_rle(urle))

    @staticmethod
    def from_polygons(
        polygons: list[list],
        height: int,
        width: int,
    ) -> "CompressedRLE":
        """Create compressed RLE mask from polygons.

        Args:
            polygons (list[list]): Mask as polygons
            height (int): Image height
            width (int): Image width

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        return CompressedRLE.from_dict(
            image_utils.polygons_to_rle(polygons, height, width)
        )

    @staticmethod
    def encode(
        mask: list[list] | dict[str, list[int]], height: int, width: int
    ) -> "CompressedRLE":
        """Create compressed RLE mask from polygons / uncompressed RLE / compressed RLE.

        Args:
            mask (list[list] | dict[str, list[int]]):
                Mask as polygons / uncompressed RLE / compressed RLE
            height (int): Image height
            width (int): Image width

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        return CompressedRLE.from_dict(image_utils.encode_rle(mask, height, width))
