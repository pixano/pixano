# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any

import numpy as np
from PIL import Image as pil_image
from pydantic import model_validator
from typing_extensions import Self

from pixano.datasets.utils import image as image_utils
from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class CompressedRLE(Annotation):
    """Compressed RLE mask type.

    Attributes:
        size: Mask size.
        counts: Mask RLE encoding.
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
    def none(cls) -> Self:
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            "None" `CompressedRLE`.
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
            Mask as NumPy array.
        """
        return image_utils.rle_to_mask({"size": self.size, "counts": self.counts})

    def to_urle(self) -> dict[str, list[int]]:
        """Convert compressed RLE mask to uncompressed RLE.

        Returns:
            Mask as uncompressed RLE.
        """
        return image_utils.rle_to_urle(self.model_dump())

    def to_polygons(self) -> list[list]:
        """Convert compressed RLE mask to poylgons.

        Returns:
            Mask as polygons.
        """
        return image_utils.rle_to_polygons(self.model_dump())

    @staticmethod
    def from_mask(mask: pil_image.Image | np.ndarray, **kwargs: Any) -> "CompressedRLE":
        """Create compressed RLE mask from NumPy array.

        Args:
            mask: Mask as NumPy array.
            kwargs: Additional arguments.

        Returns:
            Compressed RLE mask.
        """
        rle = image_utils.mask_to_rle(mask)
        return CompressedRLE(size=rle["size"], counts=rle["counts"], **kwargs)

    @staticmethod
    def from_urle(urle: dict[str, list[int]], **kwargs: Any) -> "CompressedRLE":
        """Create compressed RLE mask from uncompressed RLE.

        Args:
            urle: Mask as uncompressed RLE.
            kwargs: Additional arguments.

        Returns:
            Compressed RLE mask.
        """
        return CompressedRLE(**image_utils.urle_to_rle(urle), **kwargs)

    @staticmethod
    def from_polygons(
        polygons: list[list],
        height: int,
        width: int,
        **kwargs: Any,
    ) -> "CompressedRLE":
        """Create compressed RLE mask from polygons.

        Args:
            polygons: Mask as polygons.
            height: Image height.
            width: Image width.
            kwargs: Additional arguments.

        Returns:
            Compressed RLE mask.
        """
        return CompressedRLE(**image_utils.polygons_to_rle(polygons, height, width), **kwargs)

    @staticmethod
    def encode(mask: list[list] | dict[str, list[int]], height: int, width: int, **kwargs: Any) -> "CompressedRLE":
        """Create compressed RLE mask from polygons / uncompressed RLE / compressed RLE.

        Args:
            mask: Mask as polygons / uncompressed RLE / compressed RLE.
            height: Image height.
            width: Image width.
            kwargs: Additional arguments.

        Returns:
            Compressed RLE mask.
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
        size: Mask size.
        counts: Mask RLE encoding.
        id: CompressedRLE ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.

    Returns:
        Compressed RLE instance.
    """
    return CompressedRLE(size=size, counts=counts, id=id, item_ref=item_ref, view_ref=view_ref, entity_ref=entity_ref)
