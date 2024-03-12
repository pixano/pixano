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

from pixano.core.types.group import TableGroup


class DatasetSchema(BaseModel):
    """DatasetSchema.

    Attributes:
        schemas (dict[str, dict[str, str]]): The groups of table
        _path (Path | S3Path): Dataset path
    """

    schemas: dict[str, dict[str, str]]
    _path: Path | S3Path = PrivateAttr()

    def save(self):
        """Save DatasetSchema to json file."""
        with open(self._path / "schema.json", "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f)

    def load(self):
        """Load DatasetSchema from json file."""
        with open(self._path / "schema.json", "r", encoding="utf-8") as f:
            schema_json = json.load(f)

        schema = DatasetSchema.validate(schema_json)

        return schema

    @staticmethod
    def format_table_name(table_name: str) -> str:
        """Format table name.

        Args:
            table_name (str): Table name

        Returns:
            str: Formatted table name
        """
        return table_name.lower().replace(" ", "_")

    @staticmethod
    def format_table_names(schema_json: dict[str : dict[str, str]]):
        """Format table names."""
        for group in schema_json.keys():
            keys = list(schema_json[group].keys())
            for table in keys:
                formatted_table_name = DatasetSchema.format_table_name(table)
                schema_json[group][formatted_table_name] = schema_json[group].pop(table)
        return schema_json

    @staticmethod
    def validate(schema_json: dict, *args, **kwargs) -> "DatasetSchema":  # noqa: D417
        """Validate DatasetSchema from json.

        Args:
            schema_json (dict): JSON.

        Returns:
            DatasetSchema: DatasetSchema
        """
        for key in schema_json["schemas"].keys():
            try:
                TableGroup(key)
            except ValueError:
                raise ValueError(f"Invalid table group {key}")

        schema_json = DatasetSchema.format_table_names(schema_json)

        if any(
            key not in schema_json["schemas"].keys()
            for key in [TableGroup.ITEM.value, TableGroup.VIEW.value]
        ):
            raise ValueError("Schema should contain item and views")
        if list(schema_json["schemas"][TableGroup.ITEM.value].keys()) != [
            TableGroup.ITEM.value
        ]:
            raise ValueError(
                f"{TableGroup.ITEM.value} group should contain only one table "
                f"named {TableGroup.ITEM.value}"
            )

        return DatasetSchema.model_validate(schema_json, *args, **kwargs)

    @staticmethod
    def from_json(
        json_fp: Path | S3Path,
    ) -> "DatasetSchema":
        """Read DatasetSchema from JSON file.

        Args:
            json_fp (Path | S3Path): JSON file path

        Returns:
            DatasetSchema: DatasetSchema
        """
        if isinstance(json_fp, S3Path):
            with json_fp.open(encoding="utf-8") as json_file:
                schema_json = json.load(json_file)
        else:
            with open(json_fp, encoding="utf-8") as json_file:
                schema_json = json.load(json_file)

        schema = DatasetSchema.validate(schema_json)
        schema._path = json_fp.parent

        return schema
