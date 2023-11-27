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
from pydantic import BaseModel

from pixano.core import Image
from pixano.data.dataset_info import DatasetInfo, DatasetStat


class Dataset(BaseModel):
    """Dataset

    Attributes:
        path (Path): Dataset path
        info (DatasetInfo, optional): Dataset info
        stats (list[DatasetStat], optional): Dataset stat
        thumbnail (str, optional): Dataset thumbnail base 64 URL
    """

    path: Path
    info: Optional[DatasetInfo] = None
    stats: Optional[list[DatasetStat]] = None
    thumbnail: Optional[str] = None

    def __init__(
        self,
        path: Path,
    ):
        """Initialize dataset

        Args:
            path (Path): Dataset path
        """

        info_file = path / "db.json"
        stats_file = path / "stats.json"
        thumb_file = path / "preview.png"

        # Define public attributes through Pydantic BaseModel
        super().__init__(
            path=path,
            info=DatasetInfo.from_json(info_file),
            stats=DatasetStat.from_json(stats_file) if stats_file.is_file() else None,
            thumbnail=Image(uri=thumb_file.absolute().as_uri()).url
            if thumb_file.is_file()
            else None,
        )

    @property
    def media_dir(self) -> Path:
        """Return dataset media directory

        Returns:
            Path: Dataset media directory
        """

        return self.path / "media"

    def load_info(
        self,
        load_stats: bool = False,
        load_thumbnail: bool = False,
    ) -> DatasetInfo:
        """Return dataset info with thumbnail and stats inside

        Args:
            load_stats (bool, optional): Load dataset stats. Defaults to False.
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.

        Returns:
            DatasetInfo: Dataset info
        """

        return DatasetInfo.from_json(
            self.path / "db.json",
            load_stats=load_stats,
            load_thumbnail=load_thumbnail,
        )

    def save_info(self):
        """Save updated dataset info"""

        self.info.save(self.path)

    def connect(self) -> lancedb.DBConnection:
        """Connect to dataset with LanceDB

        Returns:
            lancedb.DBConnection: Dataset LanceDB connection
        """

        return lancedb.connect(self.path)

    @staticmethod
    def find(
        id: str,
        directory: Path,
    ) -> "Dataset":
        """Find Dataset in directory

        Args:
            id (str): Dataset ID
            directory (Path): Directory to search in

        Returns:
            Dataset: Dataset
        """

        # Browse directory
        for json_fp in directory.glob("*/db.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                # Return dataset
                return Dataset(json_fp.parent)
