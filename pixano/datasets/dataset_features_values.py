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


class DatasetFeaturesValues(BaseModel):
    """DatasetFeaturesValues.

    Attributes:
        items (dict[str, list]): Dataset tables
        views (dict[str, list]): Dataset views
        objects (dict[str, list]): Dataset objects
    """

    items: dict[str, list] = {}
    views: dict[str, list] = {}
    objects: dict[str, list] = {}

    def to_json(self, json_fp: Path):
        """Save DatasetFeaturesValues to json file."""
        json_fp.write_text(json.dumps(self.model_dump()), encoding="utf-8")

    @staticmethod
    def from_json(json_fp: Path):
        """Load DatasetFeaturesValues from json file."""
        fv_json = json.loads(json_fp.read_text(encoding="utf-8"))
        fv = DatasetFeaturesValues.model_validate(fv_json)

        return fv
