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

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from s3path import S3Path

from pixano.core import Image
from pixano.data.dataset.dataset_category import DatasetCategory
from pixano.data.dataset.dataset_stat import DatasetStat
from pixano.data.dataset.dataset_table import DatasetTable


class DatasetInfo(BaseModel):
    """DatasetInfo

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        estimated_size (str): Dataset estimated size
        num_elements (int): Number of elements in dataset
        splits (list[str]): Dataset splits
        tables (dict[str, list[DatasetTable]]): Dataset tables
        categories (list[DatasetCategory], optional): Dataset categories
        preview (str, optional): Dataset preview
        stats (list[DatasetStat], optional): Dataset stats
    """

    id: str
    name: str
    description: str
    estimated_size: str
    num_elements: int
    splits: list[str]
    tables: dict[str, list[DatasetTable]]
    categories: Optional[list[DatasetCategory]] = None
    preview: Optional[str] = None
    stats: Optional[list[DatasetStat]] = None

    def save(self, save_dir: Path | S3Path):
        """Save DatasetInfo to json file

        Args:
            save_dir (Path | S3Path): Save directory
        """

        with open(save_dir / "db.json", "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f)

    @staticmethod
    def from_json(
        json_fp: Path | S3Path,
        load_stats: bool = False,
        load_thumbnail: bool = False,
    ) -> "DatasetInfo":
        """Read DatasetInfo from JSON file

        Args:
            json_fp (Path | S3Path): JSON file path
            load_stats (bool, optional): Load dataset stats. Defaults to False.
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.

        Returns:
            DatasetInfo: DatasetInfo
        """

        if isinstance(json_fp, S3Path):
            with json_fp.open(encoding="utf-8") as json_file:
                info_json = json.load(json_file)
        else:
            with open(json_fp, encoding="utf-8") as json_file:
                info_json = json.load(json_file)

        info = DatasetInfo.model_validate(info_json)

        # Load dataset stats file
        if load_stats:
            stats_fp = json_fp.parent / "stats.json"
            if stats_fp.is_file():
                info.stats = DatasetStat.from_json(stats_fp)

        # Load thumbnail
        if load_thumbnail:
            thumb_fp = json_fp.parent / "preview.png"
            if thumb_fp.is_file():
                if isinstance(json_fp, S3Path):
                    info.preview = thumb_fp.get_presigned_url()
                else:
                    im = Image(uri=thumb_fp.absolute().as_uri())
                    info.preview = im.url

        return info

    @staticmethod
    def load_directory(
        directory: Path | S3Path,
        load_thumbnail: bool = False,
        load_stats: bool = False,
    ) -> list["DatasetInfo"]:
        """Load list of DatasetInfo from directory

        Args:
            directory (Path | S3Path): Directory to load
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.
            load_stats (bool, optional): Load dataset stats. Defaults to False.

        Returns:
            list[DatasetInfo]: List of DatasetInfo
        """

        infos = []

        # Browse directory
        for json_fp in sorted(directory.glob("*/db.json")):
            # Add dataset info to list
            infos.append(
                DatasetInfo.from_json(
                    json_fp,
                    load_thumbnail=load_thumbnail,
                    load_stats=load_stats,
                )
            )

        return infos
