# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

from pydantic import BaseModel


class DatasetStat(BaseModel):
    """DatasetStat.

    Attributes:
        name: Stats name.
        type: Stats type ('numerical' or 'categorical').
        histogram: Stats histogram data.
        range: Stats range.
    """

    name: str
    type: str
    histogram: list[dict[str, float | int | str]]
    range: list[int | float] | None = None

    @staticmethod
    def from_json(json_fp: Path) -> list["DatasetStat"]:
        """Read list of `DatasetStats` from JSON file.

        Args:
            json_fp: JSON file path.

        Returns:
            A list of `DatasetStat`.
        """
        stats_json = json.loads(json_fp.read_text(encoding="utf-8"))

        return [DatasetStat.model_validate(stat) for stat in stats_json]

    def to_json(self, json_fp: Path):
        """Save DatasetStats to json file.

        Replace existing histogram with same name in json_fp.

        Args:
            json_fp: Save directory.
        """
        try:
            stats_json = json.loads(json_fp.read_text(encoding="utf-8"))
        except FileNotFoundError:
            stats_json = []
        # keep all stats except the one with same name, we replace it if exist
        stats_json = [stat for stat in stats_json if stat["name"] != self.name]
        stats_json.append({"name": self.name, "type": self.type, "histogram": self.histogram, "range": self.range})

        json_fp.write_text(json.dumps(stats_json, indent=4), encoding="utf-8")
