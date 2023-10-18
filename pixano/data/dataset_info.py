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
        estimated_size (str): Dataset estimated size
        num_elements (int): Number of elements in dataset
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

    def save(self, save_dir: Path):
        """Save DatasetInfo to json file"""

        with open(save_dir / "db.json", "w", encoding="utf-8") as f:
            json.dump(self.dict(), f)
