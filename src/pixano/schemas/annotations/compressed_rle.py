# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any

import numpy as np
from PIL import Image as pil_image
from pydantic import field_serializer, field_validator, model_validator
from typing_extensions import Self

from pixano.features.utils import image as image_utils
from pixano.utils import issubclass_strict

from .per_frame_annotation import PerFrameAnnotation


class CompressedRLE(PerFrameAnnotation):
    """Compressed RLE mask type.

    Attributes:
        size: Mask size.
        counts: Mask RLE encoding.
    """

    size: list[int]
    counts: bytes

    @field_validator("counts", mode="before")
    @classmethod
    def _validate_counts(cls, value: bytes | str) -> bytes:
        if isinstance(value, str):
            value = bytes(value, "utf-8")
        return value

    @model_validator(mode="after")
    def _validate_fields(self):
        if (
            len(self.size) != 2
            and not all(isinstance(s, int) and s > 0 for s in self.size)
            and not (self.size == [0, 0] and self.counts == b"")
        ):
            raise ValueError("Mask size must have 2 elements and be positive integers or [0, 0] for empty mask.")
        return self

    @field_serializer("counts")
    def _serialize_counts(self, value: bytes) -> str:
        return str(value, "utf-8")

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" `CompressedRLE`.
        """
        return cls(
            id="",
            size=[0, 0],
            counts=b"",
        )

    @property
    def area(self) -> float:
        """Return mask area.

        Returns:
            Mask area
        """
        return image_utils.mask_area({"size": self.size, "counts": self.counts})

    def to_mask(self) -> np.ndarray:
        """Convert the compressed RLE mask to a NumPy array.

        Returns:
            The mask as a NumPy array.
        """
        return image_utils.rle_to_mask({"size": self.size, "counts": self.counts})

    def to_urle(self) -> dict[str, list[int]]:
        """Convert compressed RLE mask to uncompressed RLE.

        Returns:
            The mask as an uncompressed RLE.
        """
        return image_utils.rle_to_urle(self.model_dump())

    def to_polygons(self) -> list[list]:
        """Convert the compressed RLE mask to poylgons.

        Returns:
            The mask as polygons.
        """
        return image_utils.rle_to_polygons(self.model_dump())

    @staticmethod
    def from_mask(mask: pil_image.Image | np.ndarray, **kwargs: Any) -> "CompressedRLE":
        """Create a compressed RLE mask from a NumPy array.

        Args:
            mask: The mask as a NumPy array.
            kwargs: Additional arguments.

        Returns:
            The compressed RLE mask.
        """
        rle = image_utils.mask_to_rle(mask)
        return CompressedRLE(size=rle["size"], counts=rle["counts"], **kwargs)

    @staticmethod
    def from_urle(urle: dict[str, list[int]], **kwargs: Any) -> "CompressedRLE":
        """Create a compressed RLE mask from an uncompressed RLE.

        Args:
            urle: The mask as an uncompressed RLE.
            kwargs: Additional arguments.

        Returns:
            The compressed RLE mask.
        """
        return CompressedRLE(**image_utils.urle_to_rle(urle), **kwargs)  #  type: ignore[arg-type]

    @staticmethod
    def from_polygons(
        polygons: list[list],
        height: int,
        width: int,
        **kwargs: Any,
    ) -> "CompressedRLE":
        """Create a compressed RLE mask from polygons.

        Args:
            polygons: The mask as polygons.
            height: Image height.
            width: Image width.
            kwargs: Additional arguments.

        Returns:
            The compressed RLE mask.
        """
        return CompressedRLE(**image_utils.polygons_to_rle(polygons, height, width), **kwargs)

    @staticmethod
    def encode(mask: list[list] | dict[str, list[int]], height: int, width: int, **kwargs: Any) -> "CompressedRLE":
        """Create a compressed RLE mask from polygons / uncompressed RLE / compressed RLE.

        Args:
            mask: Mask as polygons / uncompressed RLE / compressed RLE.
            height: Image height.
            width: Image width.
            kwargs: Additional arguments.

        Returns:
            The compressed RLE mask.
        """
        return CompressedRLE(**image_utils.encode_rle(mask, height, width), **kwargs)


def is_compressed_rle(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of `CompressedRLE`."""
    return issubclass_strict(cls, CompressedRLE, strict)


def create_compressed_rle(
    size: list[int],
    counts: bytes,
    id: str = "",
    record_id: str = "",
    view_id: str = "",
    entity_id: str = "",
    source_type: str = "",
    source_name: str = "",
    source_metadata: str = "{}",
    tracklet_id: str = "",
    entity_dynamic_state_id: str = "",
    frame_id: str = "",
    frame_index: int = -1,
) -> CompressedRLE:
    """Create a `CompressedRLE` instance.

    Args:
        size: Mask size.
        counts: Mask RLE encoding.
        id: `CompressedRLE` ID.
        record_id: Record ID.
        view_id: View ID.
        entity_id: Entity ID.
        source_type: Source type.
        source_name: Source name.
        source_metadata: Source metadata (JSON string).
        tracklet_id: Tracklet ID.
        entity_dynamic_state_id: Entity dynamic state ID.
        frame_id: Frame/view row ID.
        frame_index: Frame index.

    Returns:
        The compressed RLE instance.
    """
    return CompressedRLE(
        size=size,
        counts=counts,
        id=id,
        record_id=record_id,
        view_id=view_id,
        entity_id=entity_id,
        source_type=source_type,
        source_name=source_name,
        source_metadata=source_metadata,
        tracklet_id=tracklet_id,
        entity_dynamic_state_id=entity_dynamic_state_id,
        frame_id=frame_id,
        frame_index=frame_index,
    )
