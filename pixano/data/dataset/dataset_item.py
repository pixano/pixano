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
from typing import Optional

import lancedb
import pyarrow as pa
from pydantic import BaseModel

from pixano.data.dataset.dataset_info import DatasetInfo
from pixano.data.fields import Fields
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

    def add_or_update_object(
        self,
        ds_table: lancedb.db.LanceTable,
        obj: ItemObject,
    ):
        """Add or update object in dataset item

        Args:
            ds_table (lancedb.db.LanceTable): Object table
            obj (ItemObject): Object to add or update
        """

        # Remove keys not in schema
        pyarrow_obj = obj.to_pyarrow()
        for key in list(pyarrow_obj):
            if key not in ds_table.schema.names:
                pyarrow_obj.pop(key)

        # Look for existing object
        scanner = ds_table.to_lance().scanner(filter=f"id in ('{obj.id}')")
        existing_obj = scanner.to_table()

        # If object exists
        if existing_obj.num_rows > 0:
            ds_table.delete(f"id in ('{obj.id}')")

        # Add object
        table_obj = pa.Table.from_pylist(
            [pyarrow_obj],
            schema=ds_table.schema,
        )
        ds_table.add(table_obj, mode="append")

        # Clear change history to prevent dataset from becoming too large
        ds_table.to_lance().cleanup_old_versions()

    def delete_objects(
        self,
        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]],
        current_obj_tables: dict[str, list],
    ):
        """Delete remove objects from dataset item

        Args:
            ds_tables (dict[str, dict[str, lancedb.db.LanceTable]]): Dataset tables
            current_obj_tables (dict[str, list]): Current item objects tables
        """

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
