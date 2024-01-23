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

from pathlib import Path
from typing import Any, Optional

import lancedb
import pyarrow as pa
from pydantic import BaseModel

from pixano.data.dataset.dataset_info import DatasetInfo
from pixano.data.fields import Fields, field_to_python
from pixano.data.item import ItemEmbedding, ItemFeature, ItemObject, ItemView


class DatasetItem(BaseModel):
    """DatasetItem

    Attributes:
        id (str): Item ID
        split (str): Item split
        features (dict[str, ItemFeature], optional): Item features
        views (dict[str, ItemView], optional): Item views
        objects (dict[str, ItemObject], optional): Item objects
        embeddings (dict[str, ItemEmbedding], optional): Item embeddings
    """

    id: str
    split: str
    features: Optional[dict[str, ItemFeature]] = None
    views: Optional[dict[str, ItemView]] = None
    objects: Optional[dict[str, ItemObject]] = None
    embeddings: Optional[dict[str, ItemEmbedding]] = None

    @staticmethod
    def from_pyarrow(
        pyarrow_item: dict[str, dict[str, pa.Table]],
        info: DatasetInfo,
        media_dir: Path,
        media_features: bool = False,
        model_id: str = None,
    ) -> "DatasetItem":
        """Format PyArrow item

        Args:
            pyarrow_item (dict[str, dict[str, pa.Table]]): PyArrow item
            info (DatasetInfo): Dataset info
            media_dir (Path): Dataset media directory
            media_features (bool, optional): Load media features like image width and height (slow for large item batches)
            model_id (str, optional): Model ID (ONNX file path) of embeddings to load. Defaults to None.

        Returns:
            DatasetItem: Formatted item
        """

        item_info = pyarrow_item["main"]["db"].to_pylist()[0]

        # Create item
        item = DatasetItem(
            id=item_info["id"],
            split=item_info["split"],
        )

        for group_name, table_group in info.tables.items():
            # Main table
            if group_name == "main":
                # Item features
                item.features = ItemFeature.from_pyarrow(
                    pyarrow_item["main"]["db"],
                    Fields(table_group[0].fields).to_schema(),
                )

            # Media tables
            if group_name == "media" and "media" in pyarrow_item:
                item.views = {}
                for table in table_group:
                    item.views = item.views | ItemView.from_pyarrow(
                        pyarrow_item["media"][table.name],
                        Fields(table.fields).to_schema(),
                        media_dir,
                        media_features,
                    )

            # Objects
            if group_name == "objects" and "objects" in pyarrow_item:
                item.objects = {}
                for table in table_group:
                    item.objects = item.objects | ItemObject.from_pyarrow(
                        pyarrow_item["objects"][table.name],
                        Fields(table.fields).to_schema(),
                        table.source,
                    )

            # Active Learning
            if group_name == "active_learning" and "active_learning" in pyarrow_item:
                for table in table_group:
                    al_features = ItemFeature.from_pyarrow(
                        pyarrow_item["active_learning"][table.name],
                        Fields(table.fields).to_schema(),
                    )
                    item.features = item.features | al_features

            # Segmentation embeddings
            if group_name == "embeddings" and "embeddings" in pyarrow_item:
                item.embeddings = {}
                for table in table_group:
                    if table.source.lower() in model_id.lower():
                        item.embeddings = item.embeddings | ItemEmbedding.from_pyarrow(
                            pyarrow_item["embeddings"][table.name],
                            Fields(table.fields).to_schema(),
                        )

        return item

    def to_pyarrow(self) -> dict[str, Any]:
        """Return DatasetItem in PyArrow format

        Returns:
            dict[str, Any]: Item in PyArrow format
        """

        pyarrow_item = {}

        # ID
        pyarrow_item["id"] = self.id
        pyarrow_item["split"] = self.split

        # Features
        if self.features is not None:
            # Add features
            for feat in self.features.values():
                pyarrow_item[feat.name] = (
                    field_to_python(feat.dtype)(feat.value)
                    if feat.value is not None
                    else None
                )

            # Check feature types
            for feat in self.features.values():
                if pyarrow_item[feat.name] is not None and not isinstance(
                    pyarrow_item[feat.name], field_to_python(feat.dtype)
                ):
                    raise ValueError(
                        f"Feature {feat.name} of object {self.id} is of type {type(self.features[feat.name].value)} instead of type {field_to_python(feat.dtype)}"
                    )

        return pyarrow_item

    def update(
        self,
        ds_table: lancedb.db.LanceTable,
    ):
        """Update dataset item

        Args:
            ds_table (lancedb.db.LanceTable): Item table
        """

        # Convert item to PyArrow
        pyarrow_item = self.to_pyarrow()
        table_item = pa.Table.from_pylist(
            [pyarrow_item],
            schema=ds_table.schema,
        )

        # Update item
        ds_table.delete(f"id in ('{self.id}')")
        ds_table.add(table_item, mode="append")

        # Clear change history to prevent dataset from becoming too large
        ds_table.to_lance().cleanup_old_versions()

    def delete_objects(
        self,
        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]],
    ):
        """Delete remove objects from dataset item

        Args:
            ds_tables (dict[str, dict[str, lancedb.db.LanceTable]]): Dataset tables
        """

        # Get current item objects
        current_obj_tables = {}
        for table_name, table in ds_tables["objects"].items():
            media_scanner = table.to_lance().scanner(filter=f"item_id in ('{self.id}')")
            current_obj_tables[table_name] = media_scanner.to_table().to_pylist()

        # Check if objects have been deleted
        for table_name, current_obj_table in current_obj_tables.items():
            for current_obj in current_obj_table:
                # If object has been deleted
                if not any(
                    obj_id == current_obj["id"] for obj_id in self.objects.keys()
                ):
                    # Remove object from table
                    ds_tables["objects"][table_name].delete(
                        f"id in ('{current_obj['id']}')"
                    )

                    # Clear change history to prevent dataset from becoming too large
                    ds_tables["objects"][table_name].to_lance().cleanup_old_versions()
