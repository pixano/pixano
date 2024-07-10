# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np
from PIL import Image as pil_image
from pydantic import model_validator

from pixano.datasets.utils import image as image_utils
from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class CompressedRLE(Annotation):
    """Compressed RLE mask type.

    Attributes:
        size (list[int]): Mask size
        counts (bytes): Mask RLE encoding
    """

    size: list[int]
    counts: bytes

    @model_validator(mode="after")
    def _validate_fields(self):
        if (
            len(self.size) != 2
            and not all(isinstance(s, int) and s > 0 for s in self.size)
            and not (self.size == [0, 0] and self.counts == b"")
        ):
            raise ValueError("Mask size must have 2 elements and be positive integers or [0, 0] for empty mask.")
        return self

    @classmethod
    def none(cls):
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            CompressedRLE: "None" CompressedRLE
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            size=[0, 0],
            counts=b"",
        )

    def to_mask(self) -> np.ndarray:
        """Convert compressed RLE mask to NumPy array.

        Returns:
            np.ndarray: Mask as NumPy array
        """
        return image_utils.rle_to_mask({"size": self.size, "counts": self.counts})

    def to_urle(self) -> dict[str, list[int]]:
        """Convert compressed RLE mask to uncompressed RLE.

        Returns:
            dict[str, list[int]]: Mask as uncompressed RLE
        """
        return image_utils.rle_to_urle(self.model_dump())

    def to_polygons(self) -> list[list]:
        """Convert compressed RLE mask to poylgons.

        Returns:
            list[list]: Mask as polygons
        """
        return image_utils.rle_to_polygons(self.model_dump())

    @staticmethod
    def from_mask(mask: pil_image.Image | np.ndarray, **kwargs) -> "CompressedRLE":
        """Create compressed RLE mask from NumPy array.

        Args:
            mask (Image.Image | np.ndarray): Mask as NumPy array.
            kwargs: Additional arguments.

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        rle = image_utils.mask_to_rle(mask)
        return CompressedRLE(size=rle["size"], counts=rle["counts"], **kwargs)

    @staticmethod
    def from_urle(urle: dict[str, list[int]], **kwargs) -> "CompressedRLE":
        """Create compressed RLE mask from uncompressed RLE.

        Args:
            urle (dict[str, list[int]]): Mask as uncompressed RLE
            kwargs: Additional arguments.

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        return CompressedRLE(**image_utils.urle_to_rle(urle), **kwargs)

    @staticmethod
    def from_polygons(
        polygons: list[list],
        height: int,
        width: int,
        **kwargs,
    ) -> "CompressedRLE":
        """Create compressed RLE mask from polygons.

        Args:
            polygons (list[list]): Mask as polygons
            height (int): Image height
            width (int): Image width
            kwargs: Additional arguments.

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        return CompressedRLE(**image_utils.polygons_to_rle(polygons, height, width), **kwargs)

    @staticmethod
    def encode(mask: list[list] | dict[str, list[int]], height: int, width: int, **kwargs) -> "CompressedRLE":
        """Create compressed RLE mask from polygons / uncompressed RLE / compressed RLE.

        Args:
            mask (list[list] | dict[str, list[int]]): Mask as polygons / uncompressed RLE / compressed RLE
            height (int): Image height
            width (int): Image width
            kwargs: Additional arguments

        Returns:
            CompressedRLE: Compressed RLE mask
        """
        return CompressedRLE(**image_utils.encode_rle(mask, height, width), **kwargs)


def is_compressed_rle(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of CompressedRLE."""
    return issubclass_strict(cls, CompressedRLE, strict)


def create_compressed_rle(
    size: list[int],
    counts: bytes,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
) -> CompressedRLE:
    """Create a CompressedRLE instance.

    Args:
        size (list[int]): Mask size
        counts (bytes): Mask RLE encoding
        id (str, optional): CompressedRLE ID.
        item_ref (ItemRef, optional): Item reference.
        view_ref (ViewRef, optional): View reference.
        entity_ref (EntityRef, optional): Entity reference.

    Returns:
        CompressedRLE: Compressed RLE instance
    """
    return CompressedRLE(size=size, counts=counts, id=id, item_ref=item_ref, view_ref=view_ref, entity_ref=entity_ref)
