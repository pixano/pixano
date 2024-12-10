# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any, Literal

import numpy as np
from pydantic import model_validator
from typing_extensions import Self

from pixano.features.utils import boxes as bbox_utils
from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation
from .compressed_rle import CompressedRLE


@_register_schema_internal
class BBox(Annotation):
    """Bounding box using coordinates in xyxy or xywh format.

    Attributes:
        coords: List of coordinates in given format.
        format: Coordinates format, 'xyxy' or 'xywh'.
        is_normalized: True if coordinates are normalized to image size.
        confidence: Bounding box confidence if predicted. -1 if not predicted.
    """

    coords: list[float]
    format: str
    is_normalized: bool
    confidence: float = -1.0

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if len(self.coords) != 4:
            raise ValueError("Bounding box coordinates must have 4 elements.")
        elif not all(coord >= 0 for coord in self.coords):
            raise ValueError("Bounding box coordinates must be positive.")
        elif self.is_normalized and not all(0 <= coord <= 1 for coord in self.coords):
            raise ValueError("Normalized bounding box coordinates must be in [0, 1] range.")
        elif (self.confidence < 0 or self.confidence > 1) and not self.confidence == -1:
            raise ValueError("Bounding box confidence must be in [0, 1] range or -1.")
        elif self.format not in ["xyxy", "xywh"]:
            raise ValueError("Bounding box format must be 'xyxy' or 'xywh'.")
        return self

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" `BBox`.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            coords=[0.0, 0.0, 0.0, 0.0],
            format="xywh",
            is_normalized=True,
            confidence=-1,
        )

    @property
    def xyxy_coords(self) -> list[float]:
        """Return the bounding box xyxy coordinates.

        Returns:
            Coordinates in xyxy format.
        """
        return self.coords if self.format == "xyxy" else bbox_utils.xywh_to_xyxy(self.coords)

    @property
    def xywh_coords(self) -> list[float]:
        """Return the bounding box xywh coordinates.

        Returns:
            Coordinates in xywh format.
        """
        return self.coords if self.format == "xywh" else bbox_utils.xyxy_to_xywh(self.coords)

    def to_xyxy(self) -> Self:
        """Return the bounding box in xyxy format.

        Returns:
            Bounding box in xyxy format.
        """
        return BBox(
            coords=self.xyxy_coords,
            format="xyxy",
            is_normalized=self.is_normalized,
            confidence=self.confidence,
        )

    def to_xywh(self) -> Self:
        """Return the bounding box in xywh format.

        Returns:
            Bounding box in xyxy format.
        """
        return BBox(
            coords=self.xywh_coords,
            format="xywh",
            is_normalized=self.is_normalized,
            confidence=self.confidence,
        )

    def normalize(self, height: int, width: int) -> Self:
        """Return the bounding box with coordinates normalized relatively to the image size.

        Args:
            height: Image height.
            width: Image width.

        Returns:
            Bounding box with coordinates normalized relatively to the image size.
        """
        return BBox(
            coords=bbox_utils.normalize_coords(self.coords, height, width),
            format=self.format,
            is_normalized=True,
            confidence=self.confidence,
        )

    def denormalize(self, height: int, width: int) -> Self:
        """Return the bounding box with coordinates denormalized relatively to the image size.

        Args:
            height: Image height.
            width: Image width.

        Returns:
            Bounding box with coordinates denormalized relatively to the image size.
        """
        return BBox(
            coords=bbox_utils.denormalize_coords(self.coords, height, width),
            format=self.format,
            is_normalized=False,
            confidence=self.confidence,
        )

    @staticmethod
    def from_xyxy(
        xyxy: list[float],
        **kwargs: Any,
    ) -> "BBox":
        """Create a bounding box using normalized xyxy coordinates.

        Args:
            xyxy: List of coordinates in xyxy format.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox(
            coords=xyxy,
            format="xyxy",
            **kwargs,
        )

    @staticmethod
    def from_xywh(
        xywh: list[float],
        **kwargs: Any,
    ) -> "BBox":
        """Create a bounding box using normalized xywh coordinates.

        Args:
            xywh: List of coordinates in xywh format.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox(
            coords=xywh,
            format="xywh",
            **kwargs,
        )

    @staticmethod
    def from_mask(mask: np.ndarray, **kwargs: Any) -> "BBox":
        """Create a bounding box using a NumPy array mask.

        Args:
            mask: NumPy array mask.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox.from_xywh(
            xywh=bbox_utils.mask_to_bbox(mask),
            is_normalized=True,
            **kwargs,
        )

    @staticmethod
    def from_rle(
        rle: CompressedRLE,
        **kwargs: Any,
    ) -> "BBox":
        """Create a bounding box using a RLE mask.

        Args:
            rle: RLE mask.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox.from_mask(mask=rle.to_mask(), **kwargs)


@_register_schema_internal
class BBox3D(Annotation):
    """A 3D bounding Box.

    Attributes:
        coords: List of coordinates in given format.
        format: Coordinates format, 'xyzxyz' or 'xyzwhd'.
        heading: Orientation of the bounding box.
        is_normalized: True if coordinates are normalized to image size.
        confidence: Bounding box confidence if predicted. -1 if not predicted.
    """

    coords: list[float]
    format: str
    heading: list[float]
    is_normalized: bool
    confidence: float = -1.0

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(self.coords) != 6:
            raise ValueError("3D Bounding box coordinates must have 6 elements.")
        elif not all(coord >= 0 for coord in self.coords):
            raise ValueError("Bounding box coordinates must be positive.")
        elif self.is_normalized and not all(0 <= coord <= 1 for coord in self.coords):
            raise ValueError("Normalized bounding box coordinates must be in [0, 1] range.")
        elif (self.confidence < 0 or self.confidence > 1) and not self.confidence == -1:
            raise ValueError("Bounding box confidence must be in [0, 1] range or -1.")
        elif self.format not in ["xyzxyz", "xyzwhd"]:
            raise ValueError("Bounding box format must be 'xyzxyz' or 'xyzwhd'.")
        return self

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" BBox3D.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            coords=[0, 0, 0, 0, 0, 0],
            format="xyzwhd",
            heading=[0, 0, 0],
            is_normalized=True,
            confidence=-1,
        )


def is_bbox(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `BBox` or a subclass of `BBox`."""
    return issubclass_strict(cls, BBox, strict)


def is_bbox3d(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `BBox3D` or subclass of `BBox3D`."""
    return issubclass_strict(cls, BBox3D, strict)


def create_bbox(
    coords: list[float],
    format: Literal["xyxy", "xywh"],
    is_normalized: bool,
    confidence: float = -1,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> BBox:
    """Create a `BBox` instance.

    Args:
        coords: List of coordinates in given format.
        format: Coordinates format, 'xyxy' or 'xywh'.
        is_normalized: True if coordinates are normalized to image size.
        confidence: Bounding box confidence if predicted.
        id: BBox ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `BBox` instance.
    """
    return BBox(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
        coords=coords,
        format=str(format),
        is_normalized=is_normalized,
        confidence=confidence,
    )


def create_bbox3d(
    coords: list[float],
    format: Literal["xyzxyz", "xyzwhd"],
    heading: list[float],
    is_normalized: bool,
    confidence: float = -1.0,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> BBox3D:
    """Create a `BBox3D` instance.

    Args:
        coords: The 3D position coordinates.
        format: Coordinates format, 'xyzxyz' or 'xyzwhd'.
        heading: The orientation.
        is_normalized: True if coordinates are normalized to image size.
        confidence: Bounding box confidence if predicted.
        id: BBox3D ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `BBox3D` instance.
    """
    return BBox3D(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
        coords=coords,
        format=str(format),
        heading=heading,
        is_normalized=is_normalized,
        confidence=confidence,
    )
