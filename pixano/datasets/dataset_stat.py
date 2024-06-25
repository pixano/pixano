# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

from pydantic import BaseModel
from s3path import S3Path


class DatasetStat(BaseModel):
    """DatasetStat.

    Attributes:
        name (str): Stats name
        type (str): Stats type ('numerical' or 'categorical')
        histogram (str): Stats histogram data
    """

    name: str
    type: str
    histogram: list[dict[str, float | int | str]]
    range: list[int | float] | None = None

    @staticmethod
    def from_json(json_fp: Path | S3Path) -> list["DatasetStat"]:
        """Read list of DatasetStats from JSON file.

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
        """Save DatasetInfo to json file.

        Replace existing histogram with same name in json_fp.

        Args:
            save_dir (Path | S3Path): Save directory
        """
        try:
            stats_json = json.load(open(save_dir, "r", encoding="utf-8"))
        except FileNotFoundError:
            stats_json = []
        # keep all stats except the one with same name, we replace it if exist
        stats_json = [stat for stat in stats_json if stat["name"] != self.name]
        stats_json.append(
            {"name": self.name, "type": self.type, "histogram": self.histogram}
        )

        json.dump(stats_json, open(save_dir, "w", encoding="utf-8"), indent="\t")
