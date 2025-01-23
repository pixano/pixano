# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import lancedb
from pydantic import ConfigDict

from pixano.datasets import DatasetInfo
from pixano.datasets.dataset import Dataset
from pixano.features.schemas.schema_group import SchemaGroup


class DatasetInfoModel(DatasetInfo):
    """Dataset info model.

    It contains all the information as a [DatasetInfo][pixano.datasets.dataset_info.DatasetInfo] and the number of
    items in the dataset.

    Attributes:
        num_items: Number of items in the dataset.
    """

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "dataset_id",
                    "name": "Dataset name",
                    "description": "Dataset description",
                    "size": "Unknown",
                    "preview": "path/to/preview.jpg",
                    "num_items": 100,
                    "workspace": "image",
                }
            ]
        },
    )

    num_items: int

    @staticmethod
    def from_dataset_info(dataset_info: DatasetInfo, dataset_dir: Path) -> "DatasetInfoModel":
        """Create a dataset info model from a dataset info.

        Args:
            dataset_info: Dataset info.
            dataset_dir: Dataset directory.

        Returns:
            Dataset info model.
        """
        db = lancedb.connect(dataset_dir / Dataset._DB_PATH)
        item_table = db.open_table(SchemaGroup.ITEM.value)
        num_items = item_table.count_rows()
        return DatasetInfoModel(
            num_items=num_items,
            **dataset_info.model_dump(),
        )
