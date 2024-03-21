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

from pydantic import BaseModel, PrivateAttr
from s3path import S3Path


class DatasetInfo(BaseModel):
    """DatasetInfo.

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        estimated_size (str): Dataset estimated size
        num_elements (int): Number of elements in dataset
        splits (list[str]): Dataset splits
        thumbnail (str, optional): Dataset thumbnail
        _path (Path | S3Path): Dataset path
    """

    id: str
    name: str
    description: str
    estimated_size: str
    num_elements: int
    splits: list[str]
    thumbnail: Optional[str] = None
    _path: Path | S3Path = PrivateAttr()

    def save(self, save_dir: Path | S3Path):
        """Save DatasetInfo to json file.

        Args:
            save_dir (Path | S3Path): Save directory
        """
        with open(save_dir / "db.json", "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f)

    def load(self):
        """Load DatasetInfo from json file."""
        with open(self._path / "info.json", "r", encoding="utf-8") as f:
            info_json = json.load(f)

        info = DatasetInfo.model_validate(info_json)

        return info

    @staticmethod
    def from_json(
        json_fp: Path | S3Path,
        load_thumbnail: bool = False,
    ) -> "DatasetInfo":
        """Read DatasetInfo from JSON file.

        Args:
            json_fp (Path | S3Path): JSON file path
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

        info_json["_path"] = json_fp.parent
        info = DatasetInfo.model_validate(info_json)

        # Load thumbnail
        if load_thumbnail:
            thumb_fp = json_fp.parent / "thumbnail.png"
            if thumb_fp.is_file():
                if isinstance(json_fp, S3Path):
                    info.thumbnail = thumb_fp.get_presigned_url()
                else:
                    im = Image(uri=thumb_fp.absolute().as_uri())
                    info.thumbnail = im.url

        return info

    @staticmethod
    def load_directory(
        directory: Path | S3Path,
        load_thumbnail: bool = False,
    ) -> list["DatasetInfo"]:
        """Load list of DatasetInfo from directory.

        Args:
            directory (Path | S3Path): Directory to load
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.
            load_stats (bool, optional): Load dataset stats. Defaults to False.

        Returns:
            list[DatasetInfo]: List of DatasetInfo
        """
        infos = []

        # Browse directory
        for json_fp in sorted(directory.glob("*/info.json")):
            # Add dataset info to list
            infos.append(
                DatasetInfo.from_json(
                    json_fp,
                    load_thumbnail=load_thumbnail,
                )
            )

        return infos
