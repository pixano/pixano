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
        features (list[ItemFeature], optional): Item features
        image (list[ItemView], optional): Item image views
        video (list[ItemView], optional): Item video views
        point_cloud (list[ItemView], optional): Item point cloud views
        objects (list[ItemObject], optional): Item objects
        embeddings (list[ItemEmbedding], optional): Item embeddings
    """

    id: str
    split: str
    features: Optional[list[ItemFeature]] = None
    image: Optional[list[ItemView]] = None
    video: Optional[list[ItemView]] = None
    point_cloud: Optional[list[ItemView]] = None
    objects: Optional[list[ItemObject]] = None
    embeddings: Optional[list[ItemEmbedding]] = None

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
            model_id (str, optional): Model ID of embeddings to load. Defaults to None.

        Returns:
            DatasetItem: Formatted item
        """

        item_info = pyarrow_item["main"]["db"].to_pylist()[0]

        # Create item
        item = DatasetItem(
            id=item_info["id"],
            split=item_info["split"],
        )

        for table_type, table_group in info.tables.items():
            # Main table
            if table_type == "main":
                for table in table_group:
                    if table["name"] == "db":
                        # Item features
                        item.features = ItemFeature.from_pyarrow(
                            pyarrow_item["main"]["db"],
                            Fields(table["fields"]).to_schema(),
                        )

            # Media tables
            if table_type == "media" and "media" in pyarrow_item:
                for table in table_group:
                    # Image table
                    if table["name"] == "image":
                        item.image = ItemView.from_pyarrow(
                            pyarrow_item["media"][table["name"]],
                            Fields(table["fields"]).to_schema(),
                            media_dir,
                        )
                    # Video table
                    elif table["name"] == "video":
                        item.video = ItemView.from_pyarrow(
                            pyarrow_item["media"][table["name"]],
                            Fields(table["fields"]).to_schema(),
                            media_dir,
                        )
                    # Point cloud table
                    elif table["name"] == "point_cloud":
                        item.point_cloud = ItemView.from_pyarrow(
                            pyarrow_item["media"][table["name"]],
                            Fields(table["fields"]).to_schema(),
                            media_dir,
                        )

            # Objects
            if table_type == "objects" and "objects" in pyarrow_item:
                item.objects = []
                for table in table_group:
                    item.objects.extend(
                        ItemObject.from_pyarrow(
                            pyarrow_item["objects"][table["source"]],
                            Fields(table["fields"]).to_schema(),
                            table["source"],
                        )
                    )

            # Active Learning
            if table_type == "active_learning" and "active_learning" in pyarrow_item:
                for table in table_group:
                    al_features = ItemFeature.from_pyarrow(
                        pyarrow_item["active_learning"][table["source"]],
                        Fields(table["fields"]).to_schema(),
                    )
                    item.features.extend(al_features)

            # Segmentation embeddings
            if table_type == "embeddings" and "embeddings" in pyarrow_item:
                item.embeddings = []
                for table in table_group:
                    if model_id in table["source"]:
                        item.embeddings.extend(
                            ItemEmbedding.from_pyarrow(
                                pyarrow_item["embeddings"][table["source"]],
                                Fields(table["fields"]).to_schema(),
                            )
                        )

        return item
