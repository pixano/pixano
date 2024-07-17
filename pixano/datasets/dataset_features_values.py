# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

from pydantic import BaseModel


class DatasetFeaturesValues(BaseModel):
    """DatasetFeaturesValues.

    Attributes:
        items (dict[str, list]): Dataset tables
        views (dict[str, list]): Dataset views
        entities (dict[str, list]): Dataset entities
        annotations (dict[str, list]): Dataset annotations
    """

    items: dict[str, list] = {}
    views: dict[str, list] = {}
    entities: dict[str, list] = {}
    annotations: dict[str, list] = {}

    def to_json(self, json_fp: Path) -> None:
        """Save DatasetFeaturesValues to json file."""
        json_fp.write_text(json.dumps(self.model_dump(), indent=4), encoding="utf-8")

    @staticmethod
    def from_json(json_fp: Path) -> "DatasetFeaturesValues":
        """Load DatasetFeaturesValues from json file."""
        fv_json = json.loads(json_fp.read_text(encoding="utf-8"))
        fv = DatasetFeaturesValues.model_validate(fv_json)

        return fv
