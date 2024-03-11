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
# http://www.cecill.summary

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, PrivateAttr
from s3path import S3Path

from pixano.core import Image


class DatasetSummary(BaseModel):
    """DatasetSummary.

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        estimated_size (str): Dataset estimated size
        num_elements (int): Number of elements in dataset
        splits (list[str]): Dataset splits
        preview (str, optional): Dataset preview
        _path (Path | S3Path): Dataset path
    """

    id: str
    name: str
    description: str
    estimated_size: str
    num_elements: int
    splits: list[str]
    preview: Optional[str] = None
    _path: Path | S3Path = PrivateAttr()

    def save(self):
        """Save DatasetSummary to json file."""
        with open(self._path / "summary.json", "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f)

    def load(self):
        """Load DatasetSummary from json file."""
        with open(self._path / "summary.json", "r", encoding="utf-8") as f:
            summary_json = json.load(f)

        summary = DatasetSummary.model_validate(summary_json)

        return summary

    @staticmethod
    def from_json(
        json_fp: Path | S3Path,
        load_thumbnail: bool = False,
    ) -> "DatasetSummary":
        """Read DatasetSummary from JSON file.

        Args:
            json_fp (Path | S3Path): JSON file path
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.

        Returns:
            DatasetSummary: DatasetSummary
        """
        if isinstance(json_fp, S3Path):
            with json_fp.open(encoding="utf-8") as json_file:
                summary_json = json.load(json_file)
        else:
            with open(json_fp, encoding="utf-8") as json_file:
                summary_json = json.load(json_file)

        summary_json["_path"] = json_fp.parent
        summary = DatasetSummary.model_validate(summary_json)

        # Load thumbnail
        if load_thumbnail:
            thumb_fp = json_fp.parent / "preview.png"
            if thumb_fp.is_file():
                if isinstance(json_fp, S3Path):
                    summary.preview = thumb_fp.get_presigned_url()
                else:
                    im = Image(uri=thumb_fp.absolute().as_uri())
                    summary.preview = im.url

        return summary

    @staticmethod
    def load_directory(
        directory: Path | S3Path,
        load_thumbnail: bool = False,
        load_stats: bool = False,
    ) -> list["DatasetSummary"]:
        """Load list of DatasetSummary from directory.

        Args:
            directory (Path | S3Path): Directory to load
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.
            load_stats (bool, optional): Load dataset stats. Defaults to False.

        Returns:
            list[DatasetSummary]: List of DatasetSummary
        """
        summarys = []

        # Browse directory
        for json_fp in sorted(directory.glob("*/summary.json")):
            # Add dataset summary to list
            summarys.append(
                DatasetSummary.from_json(
                    json_fp,
                    load_thumbnail=load_thumbnail,
                    load_stats=load_stats,
                )
            )

        return summarys
