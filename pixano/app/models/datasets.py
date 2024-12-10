# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pathlib import Path
from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from pixano.app.models.dataset_info import DatasetInfoModel
from pixano.datasets import DatasetFeaturesValues, DatasetInfo, DatasetSchema
from pixano.datasets.dataset import Dataset


class DatasetModel(BaseModel):
    """The model of a dataset.

    Attributes:
        id: Dataset ID.
        path: Path to the dataset.
        previews_path: Path to the previews.
        media_dir: Path to the media directory.
        thumbnail: Path to the thumbnail.
        dataset_schema: The dataset schema.
        feature_values: The feature values of the dataset.
        info: The dataset info.
    """

    id: str
    path: Path
    previews_path: Path
    media_dir: Path
    thumbnail: Path
    dataset_schema: DatasetSchema
    feature_values: DatasetFeaturesValues
    info: DatasetInfoModel

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> Self:
        """Create a dataset model from a dataset.

        Args:
            dataset: The dataset.

        Returns:
            The dataset model.
        """
        info = DatasetInfoModel.from_dataset_info(dataset.info, dataset.path)
        return cls(
            id=dataset.info.id,
            path=dataset.path,
            previews_path=dataset.previews_path,
            media_dir=dataset.media_dir,
            thumbnail=dataset.thumbnail,
            dataset_schema=dataset.schema,
            feature_values=dataset.features_values,
            info=info,
        )

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        """Create a dataset model from a JSON object.

        Args:
            data: JSON object.

        Returns:
            Dataset model.
        """
        return cls(
            id=data["id"],
            path=Path(data["path"]),
            previews_path=Path(data["previews_path"]),
            media_dir=Path(data["media_dir"]),
            thumbnail=Path(data["thumbnail"]),
            dataset_schema=DatasetSchema.deserialize(data["dataset_schema"]),
            feature_values=DatasetFeaturesValues(**data["feature_values"]),
            info=DatasetInfoModel.from_dataset_info(DatasetInfo(**data["info"]), Path(data["path"])),
        )

    def to_dataset(self) -> Dataset:
        """Create a dataset from a dataset model."""
        return Dataset(self.path, self.media_dir)


class PaginationColumn(BaseModel):
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
        columns: column descriptions.
        rows: rows (actual data).
    """

    columns: list[PaginationColumn]
    rows: list[dict[str, Any]]
    # Note: Any is one of the allowed cell types (int, float, str, bool, Image/Video/..., graph, ...)


class PaginationInfo(BaseModel):
    """Pagination info.

    Attributes:
        current_page: current page.
        page_size: number of items per page.
        total_size: total number of items.
    """

    current_page: int
    page_size: int
    total_size: int


class DatasetBrowser(BaseModel):
    """Data for Dataset Browser page.

    Attributes:
        id: dataset id
        name: dataset name
        table_data: table data
        pagination: pagination infos
        semantic_search: list of semantic search available models
    """

    id: str
    name: str
    table_data: TableData
    pagination: PaginationInfo
    semantic_search: list[str]
