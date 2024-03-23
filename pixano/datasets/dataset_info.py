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

from pydantic import BaseModel
from s3path import S3Path


class DatasetInfo(BaseModel):
    """DatasetInfo.

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        estimated_size (str): Dataset estimated size
        num_elements (int): Number of elements in dataset
    """

    id: str = None
    name: str
    description: str
    size: str = "Unknown"
    num_elements: int = 0

    def to_json(self, path: Path | S3Path):
        """Writes the DatasetInfo object to a JSON file.

        Args:
            path (Path | S3Path): The path to the file where the DatasetInfo object will be written.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f)

    @staticmethod
    def from_json(
        json_fp: Path | S3Path,
    ) -> "DatasetInfo":
        """Read DatasetInfo from JSON file.

        Args:
            json_fp (Path | S3Path): JSON file path

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

        return info
