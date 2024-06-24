# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2024)
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

import pydantic

from ...utils import boxes as bbox_utils
from .registry import _register_type_internal


@_register_type_internal
class BBox(pydantic.BaseModel):
    """Bounding box type using coordinates in xyxy or xywh format.

    Attributes:
        coords (list[float]): List of coordinates in given format
        format (str): Coordinates format, 'xyxy' or 'xywh'
        is_normalized (bool, optional): True if coordinates are normalized to image size
        confidence (float, optional): Bounding box confidence if predicted
    """

    coords: list[float]
    format: str
    is_normalized: bool
    confidence: float

    @staticmethod
    def none():
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value

        Returns:
            BBox: "None" BBox
        """
        return BBox(
            coords=[0.0, 0.0, 0.0, 0.0], format="xywh", is_normalized=True, confidence=0
        )

    @property
    def xyxy_coords(self) -> list[float]:
        """Return bounding box xyxy coordinates.

        Returns:
            list[float]: Coordinates in xyxy format
        """
        return (
            self.coords
            if self.format == "xyxy"
            else bbox_utils.xywh_to_xyxy(self.coords)
        )

    @property
    def xywh_coords(self) -> list[float]:
        """Return bounding box xywh coordinates.

        Returns:
            list[float]: Coordinates in xywh format
        """
        return (
            self.coords
            if self.format == "xywh"
            else bbox_utils.xyxy_to_xywh(self.coords)
        )

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
    def from_xyxy(xyxy: list[float], confidence: float = None) -> "BBox":
        """Create bounding box using normalized xyxy coordinates.

        Args:
            xyxy (list[float]): List of coordinates in xyxy format
            confidence (float, optional): Bounding box confidence if predicted.
                Defaults to None.

        Returns:
            Bbox: Bounding box
        """
        return BBox(coords=xyxy, format="xyxy", confidence=confidence)

    @staticmethod
    def from_xywh(xywh: list[float], confidence: float = None) -> "BBox":
        """Create bounding box using normalized xywh coordinates.

        Args:
            xywh (list[float]): List of coordinates in xywh format
            confidence (float, optional): Bounding box confidence if predicted.
                Defaults to None.

        Returns:
            Bbox: Bounding box
        """
        return BBox(coord=xywh, format="xywh", confidence=confidence)

    # @staticmethod
    # def from_mask(mask: np.ndarray) -> "BBox":
    #     """Create bounding box using a NumPy array mask

    #     Args:
    #         mask (np.ndarray): NumPy array mask

    #     Returns:
    #         Bbox: Bounding box
    #     """

    #     return BBox.from_xywh(mask_to_bbox(mask))

    # @staticmethod
    # def from_rle(rle: CompressedRLE) -> "BBox":
    #     """Create bounding box using a RLE mask

    #     Args:
    #         rle (CompressedRLE): RLE mask

    #     Returns:
    #         Bbox: Bounding box
    #     """

    #     return BBox.from_mask(rle.to_mask())


def is_bbox(cls: type) -> bool:
    """Check if a class is a subclass of BBox.

    Parameters:
        cls (type): The class to check.

    Returns:
        bool: True if the class is a subclass of BBox, False otherwise.
    """
    return issubclass(cls, BBox)
