# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Literal

import numpy as np
from pydantic import model_validator

from pixano.datasets.utils import boxes as bbox_utils
from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation
from .compressed_rle import CompressedRLE


@_register_schema_internal
class BBox(Annotation):
    """Bounding box type using coordinates in xyxy or xywh format.

    Attributes:
        coords (list[float]): List of coordinates in given format
        format (str): Coordinates format, 'xyxy' or 'xywh'
        is_normalized (bool): True if coordinates are normalized to image size
        confidence (float, optional): Bounding box confidence if predicted. -1 if not predicted.
    """

    coords: list[float]
    format: str
    is_normalized: bool
    confidence: float = -1.0

    @model_validator(mode="after")
    def _validate_fields(self):
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
    def none(cls):
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            BBox: "None" BBox
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
        """Return bounding box xyxy coordinates.

        Returns:
            list[float]: Coordinates in xyxy format
        """
        return self.coords if self.format == "xyxy" else bbox_utils.xywh_to_xyxy(self.coords)

    @property
    def xywh_coords(self) -> list[float]:
        """Return bounding box xywh coordinates.

        Returns:
            list[float]: Coordinates in xywh format
        """
        return self.coords if self.format == "xywh" else bbox_utils.xyxy_to_xywh(self.coords)

    def to_xyxy(self) -> "BBox":
        """Return bounding box in xyxy format.

        Returns:
            BBox: Bounding box in xyxy format
        """
        return BBox(
            coords=self.xyxy_coords,
            format="xyxy",
            is_normalized=self.is_normalized,
            confidence=self.confidence,
        )

    def to_xywh(self) -> "BBox":
        """Return bounding box in xywh format.

        Returns:
            BBox: Bounding box in xyxy format
        """
        return BBox(
            coords=self.xywh_coords,
            format="xywh",
            is_normalized=self.is_normalized,
            confidence=self.confidence,
        )

    def normalize(self, height: int, width: int) -> "BBox":
        """Return bounding box with coordinates normalized to image size.

        Args:
            height (int): Image height
            width (int): Image width

        Returns:
            BBox: Bounding box with coordinates normalized to image size
        """
        return BBox(
            coords=bbox_utils.normalize_coords(self.coords, height, width),
            format=self.format,
            is_normalized=True,
            confidence=self.confidence,
        )

    def denormalize(self, height: int, width: int) -> "BBox":
        """Return bounding box with coordinates denormalized from image size.

        Args:
            height (int): Image height
            width (int): Image width

        Returns:
            BBox: Bounding box with coordinates denormalized from image size
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
        **kwargs,
    ) -> "BBox":
        """Create bounding box using normalized xyxy coordinates.

        Args:
            xyxy (list[float]): List of coordinates in xyxy format
            kwargs: Additional arguments

        Returns:
            Bbox: Bounding box
        """
        return BBox(
            coords=xyxy,
            format="xyxy",
            **kwargs,
        )

    @staticmethod
    def from_xywh(
        xywh: list[float],
        **kwargs,
    ) -> "BBox":
        """Create bounding box using normalized xywh coordinates.

        Args:
            xywh (list[float]): List of coordinates in xywh format
            kwargs: Additional arguments

        Returns:
            Bbox: Bounding box
        """
        return BBox(
            coords=xywh,
            format="xywh",
            **kwargs,
        )

    @staticmethod
    def from_mask(mask: np.ndarray, **kwargs) -> "BBox":
        """Create bounding box using a NumPy array mask.

        Args:
            mask (np.ndarray): NumPy array mask
            kwargs: Additional arguments

        Returns:
            Bbox: Bounding box
        """
        return BBox.from_xywh(
            xywh=bbox_utils.mask_to_bbox(mask),
            is_normalized=True,
            **kwargs,
        )

    @staticmethod
    def from_rle(
        rle: CompressedRLE,
        **kwargs,
    ) -> "BBox":
        """Create bounding box using a RLE mask.

        Args:
            rle (CompressedRLE): RLE mask
            kwargs: Additional arguments

        Returns:
            Bbox: Bounding box
        """
        return BBox.from_mask(mask=rle.to_mask(), **kwargs)


@_register_schema_internal
class BBox3D(Annotation):
    """A 3D bounding Box.

    Attributes:
        coords (list[float]): List of coordinates in given format.
        format (str): Coordinates format, 'xyzxyz' or 'xyzwhd'.
        heading (list[float]): Orientation of the bounding box.
        is_normalized (bool): True if coordinates are normalized to image size.
        confidence (float, optional): Bounding box confidence if predicted. -1 if not predicted.
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
    def none(cls):
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            BBox3D: "None" BBox3D
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
    """Check if a class is a BBox or  a subclass of BBox."""
    return issubclass_strict(cls, BBox, strict)


def is_bbox3d(cls: type, strict: bool = False) -> bool:
    """Check if a class is a BBox3D or subclass of BBox3D."""
    return issubclass_strict(cls, BBox3D, strict)


def create_bbox(
    coords: list[float],
    format: str,
    is_normalized: bool,
    confidence: float = -1,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
) -> BBox:
    """Create a BBox instance.

    Args:
        coords (list[float]): List of coordinates in given format
        format (str): Coordinates format, 'xyxy' or 'xywh'
        is_normalized (bool): True if coordinates are normalized to image size
        confidence (float, optional): Bounding box confidence if predicted.
        id (str, optional): BBox ID.
        item_ref (ItemRef, optional): Item reference.
        view_ref (ViewRef, optional): View reference.
        entity_ref (EntityRef, optional): Entity reference.

    Returns:
        BBox: The created BBox instance.
    """
    return BBox(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        coords=coords,
        format=format,
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
) -> BBox3D:
    """Create a BBox3D instance.

    Args:
        coords (list[float]): The 3D position coordinates.
        format (Literal["xyzxyz", "xyzwhd"]): Coordinates format, 'xyzxyz' or 'xyzwhd'.
        heading (list[float]): The orientation.
        is_normalized (bool): True if coordinates are normalized to image size.
        confidence (float, optional): Bounding box confidence if predicted.
        id (str, optional): BBox3D ID.
        item_ref (ItemRef, optional): Item reference.
        view_ref (ViewRef, optional): View reference.
        entity_ref (EntityRef, optional): Entity reference.

    Returns:
        BBox3D: The created BBox3D instance.
    """
    return BBox3D(
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        coords=coords,
        format=format,
        heading=heading,
        is_normalized=is_normalized,
        confidence=confidence,
    )
