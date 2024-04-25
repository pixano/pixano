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

from .dataset_schema import DatasetSchema


class DatasetLibrary(BaseModel):
    """DatasetLibrary. Data for a dataset library card in Datasets Library page

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        estimated_size (str): Dataset estimated size
        num_elements (int): Number of elements in dataset
        preview (str): Path to a preview thumbnail
    """

    id: str = None
    name: str
    description: str
    size: str = "Unknown"
    num_elements: int = 0
    preview: str = ""

    def to_json(self, json_fp: Path):
        """Writes the DatasetInfo object to a JSON file.

        Args:
            json_fp (Path): The path to the file where the DatasetInfo object
                will be written.
        """
        json_fp.write_text(json.dumps(self.model_dump(), indent=4), encoding="utf-8")

    @staticmethod
    def from_json(
        json_fp: Path,
    ) -> "DatasetLibrary":
        """Read DatasetLibrary from JSON file.

        Args:
            json_fp (Path): JSON file path

        Returns:
            DatasetLibrary: DatasetInfo
        """
        info_json = json.loads(json_fp.read_text(encoding="utf-8"))
        info = DatasetLibrary.model_validate(info_json)

        return info

    @staticmethod
    def load_directory(
        directory: Path,
        load_thumbnail: bool = False,
        load_stats: bool = False,
    ) -> list["DatasetLibrary"]:
        """Load list of DatasetLibrary from directory

        Args:
            directory (Path): Directory to load
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.
            load_stats (bool, optional): Load dataset stats. Defaults to False.

        Returns:
            list[DatasetLibrary]: List of DatasetLibrary
        """

        library = []

        # Browse directory
        for json_fp in sorted(directory.glob("*/info.json")):
            info = DatasetLibrary.from_json(json_fp)
            library.append(
                {
                    "id": info.id,
                    "name": info.name,
                    "description": info.description,
                    "estimated_size": info.size,
                    "num_elements": info.num_elements,
                    "preview": str(
                        json_fp.parent / "previews" / (info.id + ".jpg")
                    ),  # TODO choose correct preview name / path / extension
                }
            )

        return library

    @staticmethod
    def tables_from_schema(schema: DatasetSchema):
        tables = {}
        legacy_mapping = {"item": "main", "views": "media"}
        for group in schema._groups:
            gr = (
                legacy_mapping[group.value]
                if group.value in legacy_mapping
                else group.value
            )
            tables[gr] = [
                {
                    "name": tname,
                    "fields": {},
                    "source": None,
                    "type": None,
                }
                for tname in schema._groups[group]
            ]
        return tables
