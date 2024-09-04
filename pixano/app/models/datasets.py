# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pathlib import Path
from typing import Any

from pydantic import BaseModel

from pixano.datasets import DatasetFeaturesValues, DatasetInfo, DatasetSchema
from pixano.datasets.dataset import Dataset


class DatasetModel(BaseModel):
    """Dataset model."""

    id: str
    path: Path
    previews_path: Path
    media_dir: Path
    thumbnail: Path
    schema: DatasetSchema
    feature_values: DatasetFeaturesValues
    info: DatasetInfo

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "DatasetModel":
        """Create a dataset model from a dataset.

        Args:
            dataset: Dataset.

        Returns:
            Dataset model.
        """
        raise cls(
            path=dataset.path,
            previews_path=dataset._PREVIEWS_PATH,
            media_path=dataset.media_dir,
            thumb_file=dataset.thumbnail,
            schema=dataset.schema,
            feature_values=dataset.features_values,
            info=dataset.info,
        )

    def to_dataset(self) -> Dataset:
        """Create a dataset from a dataset model."""
        return Dataset.find(self.id, self.path.parent, self.media_dir)


class ColDesc(BaseModel):
    """Column description.

    Attributes:
        name: column name.
        type: column type.
    """

    name: str
    type: str


class TableData(BaseModel):
    """Table data.

    Attributes:
        col: column descriptions.
        rows: rows (actual data).
    """

    cols: list[ColDesc]
    rows: list[dict[str, Any]]
    # Note: Any is one of the allowed cell types (int, float, str, bool, Image/Video/..., graph, ...)


class PaginationInfo(BaseModel):
    """Pagination info.

    Attributes:
        current: current page.
        size: number of items per page.
        total: total number of items.
    """

    current: int
    size: int
    total: int


class DatasetExplorer(BaseModel):
    """Data for Dataset Explorer page.

    Attributes:
        id: dataset id
        name: dataset name
        table_data: table data
        pagination: pagination infos
        sem_search: list of semantic search available models
    """

    id: str
    name: str
    table_data: TableData
    pagination: PaginationInfo
    sem_search: list[str]
