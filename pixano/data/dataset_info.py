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


class DatasetInfo(BaseModel):
    """DatasetInfo

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        estimated_size (str, optional): Dataset estimated size
        num_elements (int, optional): Number of elements in dataset
        preview (str, optional): Dataset preview
        splits (list[str]): Dataset splits
        tables (dict[str, list], optional): Dataset tables
        categories (list[dict], optional): Dataset categories
    """

    id: str
    name: str
    description: str
    estimated_size: Optional[str]
    num_elements: Optional[int]
    preview: Optional[str]
    splits: Optional[list[str]]
    tables: Optional[dict[str, list]]
    categories: Optional[list[dict]]

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        estimated_size: str = None,
        num_elements: int = None,
        preview: str = None,
        splits: list[str] = None,
        tables: dict[str, list] = None,
        categories: list[dict] = None,
    ):
        """Initialize Bounding box

        Args:
            id (str): Dataset ID
            name (str): Dataset name
            description (str): Dataset description
            estimated_size (str, optional): Dataset estimated size. Defaults to None.
            num_elements (int, optional): Number of elements in dataset. Defaults to None.
            preview (str, optional): Dataset preview. Defaults to None.
            splits (list[str]): Dataset splits. Defaults to None.
            tables (dict[str, list], optional): Dataset tables. Defaults to None.
            categories (list[dict], optional): Dataset categories. Defaults to None.
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__(
            id=id,
            name=name,
            description=description,
            estimated_size=estimated_size,
            num_elements=num_elements,
            preview=preview,
            splits=splits,
            tables=tables,
            categories=categories,
        )

    def save(self, save_dir: Path):
        """Save DatasetInfo to json file"""

        with open(save_dir / "db.json", "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f)

    @staticmethod
    def from_json(json_fp: Path) -> "DatasetInfo":
        """Read DatasetInfo from JSON file

        Args:
            json_fp (Path): JSON file path

        Returns:
            DatasetInfo: DatasetInfo
        """

        with open(json_fp) as json_file:
            info_json = json.load(json_file)

        return DatasetInfo.model_validate(info_json)
