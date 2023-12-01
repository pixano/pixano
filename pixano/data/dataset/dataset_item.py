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
        model_id: str = None,
    ) -> "DatasetItem":
        """Format PyArrow item

        Args:
            pyarrow_item (dict[str, dict[str, pa.Table]]): PyArrow item
            info (DatasetInfo): Dataset info
            media_dir (Path): Dataset media directory
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
                for table in table_group:
                    if table.name == "db":
                        # Item features
                        item.features = ItemFeature.from_pyarrow(
                            pyarrow_item["main"]["db"],
                            Fields(table.fields).to_schema(),
                        )

            # Media tables
            if group_name == "media" and "media" in pyarrow_item:
                item.views = {}
                for table in table_group:
                    item.views = item.views | ItemView.from_pyarrow(
                        pyarrow_item["media"][table.name],
                        Fields(table.fields).to_schema(),
                        media_dir,
                    )

            # Objects
            if group_name == "objects" and "objects" in pyarrow_item:
                item.objects = {}
                for table in table_group:
                    item.objects = item.objects | ItemObject.from_pyarrow(
                        pyarrow_item["objects"][table.source],
                        Fields(table.fields).to_schema(),
                        table.source,
                    )

            # Active Learning
            if group_name == "active_learning" and "active_learning" in pyarrow_item:
                for table in table_group:
                    al_features = ItemFeature.from_pyarrow(
                        pyarrow_item["active_learning"][table.source],
                        Fields(table.fields).to_schema(),
                    )
                    item.features = item.features | al_features

            # Segmentation embeddings
            if group_name == "embeddings" and "embeddings" in pyarrow_item:
                item.embeddings = {}
                for table in table_group:
                    if table.source.lower() in model_id.lower():
                        item.embeddings = item.embeddings | ItemEmbedding.from_pyarrow(
                            pyarrow_item["embeddings"][table.source],
                            Fields(table.fields).to_schema(),
                        )

        return item
