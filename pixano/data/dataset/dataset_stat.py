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


class DatasetStat(BaseModel):
    """DatasetStat

    Attributes:
        name (str): Stats name
        type (str): Stats type ('numerical' or 'categorical')
        histogram (str): Stats histogram data
    """

    name: str
    type: str
    histogram: list[dict[str, float | int | str]]
    range: Optional[list[int | float]] = None

    @staticmethod
    def from_json(json_fp: Path | S3Path) -> list["DatasetStat"]:
        """Read list of DatasetStats from JSON file

        Args:
            json_fp (Path | S3Path): JSON file path

        Returns:
            list[DatasetStats]: List of DatasetStat
        """

        if isinstance(json_fp, S3Path):
            with json_fp.open(encoding="utf-8") as json_file:
                stats_json = json.load(json_file)
        else:
            with open(json_fp, encoding="utf-8") as json_file:
                stats_json = json.load(json_file)

        return [DatasetStat.model_validate(stat) for stat in stats_json]

    def save(self, save_dir: Path | S3Path):
        """Save DatasetInfo to json file
           replace existing histogram with same name in json_fp

        Args:
            save_dir (Path | S3Path): Save directory
        """

        try:
            if isinstance(save_dir, S3Path):
                with (save_dir / "stats.json").open(encoding="utf-8") as json_file:
                    json_stats = json.load(json_file)
            else:
                with open(save_dir / "stats.json", "r", encoding="utf-8") as json_file:
                    json_stats = json.load(json_file)
        except FileNotFoundError:
            json_stats = []
        # keep all stats except the one with same name, we replace it if exist
        json_stats = [stat for stat in json_stats if stat["name"] != self.name]
        json_stats.append(
            {"name": self.name, "type": self.type, "histogram": self.histogram}
        )

        if isinstance(save_dir, S3Path):
            with (save_dir / "stats.json").open("w", encoding="utf-8") as f:
                json.dump(json_stats, f, indent="\t")
        else:
            with open(save_dir / "stats.json", "w", encoding="utf-8") as f:
                json.dump(json_stats, f, indent="\t")
