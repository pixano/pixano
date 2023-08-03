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

import pyarrow as pa
import pyarrow.dataset as ds
from pydantic import BaseModel

from pixano.core.features import Features


class DatasetInfo(BaseModel):
    """DatasetInfo

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        num_elements (int): Number of elements in dataset
        features (Features, optional): Features of dataset
        preview (str, optional): Dataset preview
        categories (list[dict], optional): Dataset categories
        model_id (str, optional): Model ID
        model_name (str, optional): Model name
        model_source (str, optional): Model source
        model_info (str, optional): Model info
    """

    id: str
    name: str
    description: str
    features: Optional[Features]
    num_elements: Optional[int]
    preview: Optional[str]
    categories: Optional[list[dict]]
    model_id: Optional[str]
    model_name: Optional[str]
    model_source: Optional[str]
    model_info: Optional[str]

    class Config:
        arbitrary_types_allowed = True

class Dataset:
    """Dataset class

    Attributes:
        _path (Path): Dataset path
        _info (DatasetInfo): Dataset info
        _partitioning (ds.partitioning): Dataset partitioning
    """

    _partitioning: ds.partitioning = ds.partitioning(
        pa.schema([("split", pa.string())]), flavor="hive"
    )

    def __init__(self, path: Path):
        """Initialize dataset

        Args:
            path (Path): Dataset path
        """

        self._path = path
        self._info = DatasetInfo.parse_file(self._path / "spec.json")

    @property
    def info(self):
        return self._info

    @property
    def path(self):
        return self._path

    @property
    def media_dir(self):
        return self._path / "media"

    def load(self):
        return ds.dataset(self._path / "db", partitioning=self._partitioning)


class InferenceDataset(Dataset):
    """Inference Dataset

    Attributes:
        _path (Path): Dataset path
        _info (DatasetInfo): Dataset info
        _partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(self, path: Path):
        self._path = path
        self._info = DatasetInfo.parse_file(self._path / "infer.json")

    def load(self):
        return ds.dataset(
            self._path, partitioning=self._partitioning, ignore_prefixes=["infer.json"]
        )


class EmbeddingDataset(Dataset):
    """Embedding Dataset

    Attributes:
        _path (Path): Dataset path
        _info (DatasetInfo): Dataset info
        _partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(self, path: Path):
        self._path = path
        self._info = DatasetInfo.parse_file(self._path / "embed.json")

    def load(self):
        return ds.dataset(
            self._path, partitioning=self._partitioning, ignore_prefixes=["embed.json"]
        )
