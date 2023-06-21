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

from pixano.transforms.boxes import normalize, xywh_to_xyxy, xyxy_to_xywh


# ------------------------------------------------
#             Python type
# ------------------------------------------------


class BBox:
    """Bounding box type using coordinates in xyxy or xywh format

    Attributes:
        _coords (list[float]): List of coordinates in given format
        _format (str): Coordinates format, 'xyxy' or 'xywh'. Defaults to 'xyxy'.
        _is_normalized (bool, optional): True if coordinates are normalized to image size. Defaults to True.
    """

    def __init__(self, coords: list[float], format: str, is_normalized: bool = True):
        """Initialize bounding box from xyxy or xywh coordinates

        Args:
            coords (list[float]): List of coordinates in given format
            format (str): Coordinates format, 'xyxy' or 'xywh'. Defaults to 'xyxy'.
            is_normalized (bool, optional): True if coordinates are normalized to image size. Defaults to True.
        """

        self._coords = coords
        self._format = format
        self._is_normalized = is_normalized

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

    @property
    def is_normalized(self) -> bool:
        """Returns bounding box coordinates normalization

        Returns:
            bool: True if coordinates are normalized to image size.
        """

        return self._is_normalized

    @property
    def format(self) -> str:
        """Returns bounding box coordinates format

        Returns:
            str: Coordinates format, 'xyxy' or 'xywh'
        """

        return self._format

    def to_xyxy(self) -> list[float]:
        """Get bounding box xyxy coordinates

        Returns:
            list[float]: Coordinates in xyxy format
        """

        if self._format == "xywh":
            return xywh_to_xyxy(self._coords)
        return self._coords

    def to_xywh(self) -> list[float]:
        """Get bounding box xywh coordinates

        Returns:
            list[float]: Coordinates in xywh format
        """

        if self._format == "xyxy":
            return xyxy_to_xywh(self._coords)
        return self._coords

    def format_xyxy(self):
        """Transform bounding box to xyxy format"""

        if self._format == "xywh":
            self._coords = xywh_to_xyxy(self._coords)
            self._format = "xyxy"

    def format_xywh(self):
        """Transform bounding box to xywh format"""

        if self._format == "xyxy":
            self._coords = xyxy_to_xywh(self._coords)
            self._format = "xywh"

    def normalize(self, height: int, width: int):
        """Normalize coordinates to image size

        Args:
            height (int): Image height
            width (int): Image width
        """

        self._coords = normalize(self._coords, height, width)

    def to_dict(self) -> dict[list[float], bool, str]:
        return {
            "coords": self._coords,
            "is_normalized": self._is_normalized,
            "format": self._format,
        }


# ------------------------------------------------
#             Py arrow integration
# ------------------------------------------------


class BBoxType(pa.ExtensionType):
    """Bounding box type as PyArrow list of PyArrow float32"""

    def __init__(self):
        super(BBoxType, self).__init__(
            pa.struct(
                [
                    pa.field("coords", pa.list_(pa.float32(), list_size=4)),
                    pa.field("is_normalized", pa.bool_()),
                    pa.field("format", pa.string()),
                ]
            ),
            "BBox",
        )

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return BBoxType()

    def __arrow_ext_serialize__(self):
        return b""

    def __arrow_ext_scalar_class__(self):
        return BBoxScalar

    def __arrow_ext_class__(self):
        return BBoxArray


class BBoxScalar(pa.ExtensionScalar):
    def as_py(self) -> BBox:
        return BBox(
            self.value["coords"].as_py(),
            self.value["format"].as_py(),
            self.value["is_normalized"].as_py(),
        )


class BBoxArray(pa.ExtensionArray):
    """Class to use pa.array for BBox instance"""

    @classmethod
    def from_BBox_list(cls, bbox_list: list[BBox]) -> pa.Array:
        """Create Bbox pa.array from bbox list

        Args:
            bbox_list (list[Bbox]): list of bbox

        Returns:
            pa.Array: pa.array of Bbox
        """
        bbox_dicts = [bbox.to_dict() for bbox in bbox_list]

        return pa.array(bbox_dicts, BBoxType())


def is_bbox_type(obj: pa.DataType) -> bool:
    """Return True if obj is an instance of BboxType

    Args:
        obj (pa.DataType): instance to check

    Returns:
        bool
    """

    return isinstance(obj, BBoxType)
