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

from typing import Any, Optional

import lancedb
import pyarrow as pa
from pydantic import BaseModel

from pixano.core import BBox, CompressedRLE
from pixano.data.fields import field_to_python
from pixano.data.item.item_feature import ItemFeature


class ItemURLE(BaseModel):
    """Uncompressed URLE mask type for DatasetItem

    Type for CompressedRLE.to_urle()

    Attributes:
        size (list[int]): Mask size
        counts (list[int]): Mask URLE encoding
    """

    size: list[int]
    counts: list[int]

    @staticmethod
    def from_pyarrow(
        rle: CompressedRLE,
    ) -> "ItemURLE":
        """Create ItemURLE from compressed RLE

        Args:
            rle (CompressedRLE): Compressed RLE

        Returns:
            ItemURLE: ItemURLE
        """

        return ItemURLE.model_validate(rle.to_urle()) if rle.counts else None

    def to_pyarrow(self) -> CompressedRLE:
        """Return ItemURLE as compressed RLE

        Returns:
            CompressedRLE: Compressed RLE
        """

        return CompressedRLE.from_urle(self.model_dump()) if self.counts else None


class ItemBBox(BaseModel):
    """BBox type for DatasetItem

    Type for BBox.to_dict()

    Attributes:
        coords (list[float]): List of coordinates in given format
        format (str): Coordinates format, 'xyxy' or 'xywh'
        is_normalized (bool, optional): True if coordinates are normalized to image size
        confidence (float, optional): Bounding box confidence if predicted
    """

    coords: list[float]
    format: str
    is_normalized: Optional[bool] = None
    confidence: Optional[float] = None

    @staticmethod
    def from_pyarrow(
        bbox: BBox,
    ) -> "ItemBBox":
        """Create ItemBBox from bounding box

        Args:
            bbox (BBox): Bounding box

        Returns:
            ItemBBox: ItemBBox
        """

        return (
            ItemBBox.model_validate(bbox.to_xywh().to_dict())
            if bbox.coords != [0.0, 0.0, 0.0, 0.0]
            else None
        )

    def to_pyarrow(self, mask: ItemURLE = None) -> BBox:
        """Return ItemBbox as BBox

        Args:
            mask (ItemURLE, optional): Mask to create BBox from in ItemBBox is empty. Defaults to None.


        Returns:
            BBox: Bounding box
        """

        return (
            BBox.from_dict(self.model_dump())
            if self.coords != [0.0, 0.0, 0.0, 0.0]
            else BBox.from_rle(mask.to_pyarrow())
            if mask
            else None
        )


class ItemObject(BaseModel):
    """Object type for DatasetItem

    Attributes:
        id (str): Object ID
        item_id (str): Object item ID
        view_id (str): Object view ID
        source_id (str): Object source ID
        bbox (ItemBBox, optional): Object bounding box
        mask (ItemURLE, optional): Object mask
        features (dict[str, ItemFeature], optional): Object features
    """

    id: str
    item_id: str
    view_id: str
    source_id: str
    bbox: Optional[ItemBBox] = None
    mask: Optional[ItemURLE] = None
    features: Optional[dict[str, ItemFeature]] = None

    @staticmethod
    def from_pyarrow(
        table: pa.Table,
        schema: pa.schema,
        source_id: str,
    ) -> dict[str, "ItemObject"]:
        """Create dictionary of ItemObject from PyArrow Table

        Args:
            table (dict[str, Any]): PyArrow table
            schema (pa.schema): PyArrow schema
            source_id (str): Objects source ID

        Returns:
            dict[str, ItemObject]: Dictionary of ItemObject
        """

        items = table.to_pylist()
        objects = {}

        # Iterate on objects
        for index, item in enumerate(items):
            # Create object
            obj = ItemObject(
                id=item["id"],
                item_id=item["item_id"],
                view_id=item["view_id"],
                source_id=source_id,
            )
            # Add bbox and mask
            for field in schema:
                if field.name == "bbox" and item["bbox"]:
                    obj.bbox = ItemBBox.from_pyarrow(item["bbox"])
                elif field.name == "mask" and item["mask"]:
                    obj.mask = ItemURLE.from_pyarrow(item["mask"])
            # Add features
            obj.features = ItemFeature.from_pyarrow(table.take([index]), schema)
            # Append object
            objects[item["id"]] = obj

        return objects

    def to_pyarrow(self) -> dict[str, Any]:
        """Return ItemObject in PyArrow format

        Returns:
            dict[str, Any]: Object in PyArrow format
        """

        pyarrow_object = {}

        # ID
        pyarrow_object["id"] = self.id
        pyarrow_object["item_id"] = self.item_id
        pyarrow_object["view_id"] = self.view_id

        # BBox and Mask
        pyarrow_mask = self.mask.to_pyarrow() if self.mask else None
        pyarrow_bbox = self.bbox.to_pyarrow(self.mask) if self.bbox else None

        pyarrow_object["mask"] = pyarrow_mask.to_dict() if pyarrow_mask else None
        pyarrow_object["bbox"] = pyarrow_bbox.to_dict() if pyarrow_bbox else None

        # Features
        if self.features is not None:
            # Add features
            for feat in self.features.values():
                pyarrow_object[feat.name] = (
                    field_to_python(feat.dtype)(feat.value)
                    if feat.value is not None
                    else None
                )

            # Check feature types
            for feat in self.features.values():
                if pyarrow_object[feat.name] is not None and not isinstance(
                    pyarrow_object[feat.name], field_to_python(feat.dtype)
                ):
                    raise ValueError(
                        f"Feature {feat.name} of object {self.id} is of type {type(self.features[feat.name].value)} instead of type {field_to_python(feat.dtype)}"
                    )

        return pyarrow_object

    def add_or_update(
        self,
        ds_table: lancedb.db.LanceTable,
    ):
        """Add or update item object

        Args:
            ds_table (lancedb.db.LanceTable): Object table
        """

        # Convert object to PyArrow
        pyarrow_obj = self.to_pyarrow()
        table_obj = pa.Table.from_pylist(
            [pyarrow_obj],
            schema=ds_table.schema,
        )

        # Delete object (if it exists)
        scanner = ds_table.to_lance().scanner(filter=f"id in ('{self.id}')")
        existing_obj = scanner.to_table()
        if existing_obj.num_rows > 0:
            ds_table.delete(f"id in ('{self.id}')")

        # Add object
        ds_table.add(table_obj, mode="append")

        # Clear change history to prevent dataset from becoming too large
        ds_table.to_lance().cleanup_old_versions()
