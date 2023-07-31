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


import pyarrow as pa
from PIL import Image
from pydantic import BaseModel

from pixano.core.arrow_types.all_pixano_types import PixanoType, createPaType
from pixano.transforms.boxes import mask_to_bbox, normalize, xywh_to_xyxy, xyxy_to_xywh

# ------------------------------------------------
#             Python type
# ------------------------------------------------


class BBox(PixanoType, BaseModel):
    """Bounding box type using coordinates in xyxy or xywh format

    Attributes:
        coords (list[float]): List of coordinates in given format
        format (str): Coordinates format, 'xyxy' or 'xywh'.
        is_normalized (bool, optional): True if coordinates are normalized to image size. Defaults to True.
    """

    coords: list[float]
    format: str
    is_normalized: bool

    def __init__(self, coords: list[float], format: str, is_normalized: bool = True):
        """Initialize bounding box from xyxy or xywh coordinates

        Args:
            coords (list[float]): List of coordinates in given format
            format (str): Coordinates format, 'xyxy' or 'xywh'.
            is_normalized (bool, optional): True if coordinates are normalized to image size. Defaults to True.
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__(coords=coords, format=format, is_normalized=is_normalized)

    @classmethod
    def from_xyxy(cls, xyxy: list[float]) -> "BBox":
        """Create bounding box using normalized xyxy coordinates

        Args:
            xyxy (list[float]): List of coordinates in xyxy format

        Returns:
            Bbox: Bounding box
        """

        return BBox(xyxy, "xyxy")

    @classmethod
    def from_xywh(cls, xywh: list[float]) -> "BBox":
        """Create bounding box using normalized xywh coordinates

        Args:
            xywh (list[float]): List of coordinates in xywh format

        Returns:
            Bbox: Bounding box
        """

        return BBox(xywh, "xywh")

    @staticmethod
    def from_mask(mask: Image.Image):
        return BBox.from_xywh(mask_to_bbox(mask))

    def to_xyxy(self) -> list[float]:
        """Get bounding box xyxy coordinates

        Returns:
            list[float]: Coordinates in xyxy format
        """

        if self.format == "xywh":
            return xywh_to_xyxy(self.coords)
        return self.coords

    def to_xywh(self) -> list[float]:
        """Get bounding box xywh coordinates

        Returns:
            list[float]: Coordinates in xywh format
        """

        if self.format == "xyxy":
            return xyxy_to_xywh(self.coords)
        return self.coords

    def format_xyxy(self):
        """Transform bounding box to xyxy format"""

        if self.format == "xywh":
            self.coords = xywh_to_xyxy(self.coords)
            self.format = "xyxy"

    def format_xywh(self):
        """Transform bounding box to xywh format"""

        if self.format == "xyxy":
            self.coords = xyxy_to_xywh(self.coords)
            self.format = "xywh"

    def normalize(self, height: int, width: int):
        """Normalize coordinates to image size

        Args:
            height (int): Image height
            width (int): Image width
        """

        self.coords = normalize(self.coords, height, width)

    @classmethod
    def to_struct(cls) -> pa.StructType:
        return pa.struct(
            [
                pa.field("coords", pa.list_(pa.float32(), list_size=4)),
                pa.field("is_normalized", pa.bool_()),
                pa.field("format", pa.string()),
            ]
        )


BBoxType = createPaType(BBox.to_struct(), "Bbox", BBox)
