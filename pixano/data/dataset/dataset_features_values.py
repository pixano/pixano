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

from pydantic import BaseModel, PrivateAttr
from s3path import S3Path


class DatasetFeaturesValues(BaseModel):
    """DatasetFeaturesValues.

    Attributes:
        items (dict[str, list]): Dataset tables
        views (dict[str, list]): Dataset views
        objects (dict[str, list]): Dataset objects
        _path (Path | S3Path): Dataset path
    """

    items: dict[str, list]
    views: dict[str, list]
    objects: dict[str, list]
    _path: Path | S3Path = PrivateAttr()

    def save(self):
        """Save DatasetFeaturesValues to json file."""
        with open(self._path / "features_values.json", "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f)

    def load(self):
        """Load DatasetFeaturesValues from json file."""
        with open(self._path / "schema.json", "r", encoding="utf-8") as f:
            schema_json = json.load(f)

        schema = DatasetFeaturesValues.model_validate(schema_json)

        return schema

    @staticmethod
    def from_json(
        json_fp: Path | S3Path,
    ) -> "DatasetFeaturesValues":
        """Read DatasetFeaturesValues from JSON file.

        Args:
            json_fp (Path | S3Path): JSON file path

        Returns:
            DatasetFeaturesValues: DatasetFeaturesValues
        """
        if isinstance(json_fp, S3Path):
            with json_fp.open(encoding="utf-8") as json_file:
                features_values_json = json.load(json_file)
        else:
            with open(json_fp, encoding="utf-8") as json_file:
                features_values_json = json.load(json_file)

        features_values_json["_path"] = json_fp.parent
        features_values = DatasetFeaturesValues.model_validate(features_values_json)

        return features_values
