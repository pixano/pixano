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

import pydantic
from lancedb.pydantic import LanceModel
from .registry import _register_table_type_internal


class ViewRecords(pydantic.BaseModel):
    """
    Represents a view record.

    Attributes:
        id (str): The ID of the view record.
        name (str): The name of the view record.
        type (ViewType): The type of the view record.
    """

    ids: list[str]
    names: list[str]
    paths: list[str]

    def get_by_id(self, id: str):
        for curr_id in self.ids:
            if curr_id == id:
                return {"id": self.id, "name": self.name, "path": self.path}
        return None

    def get_by_name(self, name: str):
        for curr_name in self.names:
            if curr_name == name:
                return {"id": self.id, "name": self.name, "path": self.path}
        return None

    @classmethod
    def from_dict(cls, data: dict):
        ids = [d["id"] for d in data]
        names = [d["name"] for d in data]
        paths = [d["path"] for d in data]
        return cls(
            ids=ids,
            names=names,
            paths=paths
        )


@_register_table_type_internal()
class Item(LanceModel):
    """Image Lance Model"""

    id: str
    views: ViewRecords
    split: str
