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

from typing import Any
from pydantic import BaseModel


class ColDesc(BaseModel):
    name: str
    type: str


class TableData(BaseModel):
    cols: list[ColDesc]
    rows: list[dict[str, Any]]   # <-- Any is one of the allowed cell types (int, float, str, bool, Image/Video/..., graph, ...)


class PaginationInfo(BaseModel):
    current: int
    size: int
    total: int


class DatasetExplorer(BaseModel):
    """Data for Dataset Explorer page

    Attributes:
        id (str): dataset id
        name (str): dataset name
        table_data (TableData): table data
        pagination (PaginationInfo): pagination infos
        sem_search (list[str]): list of semantic search available models
    """
    id: str
    name: str
    table_data: TableData
    pagination: PaginationInfo
    sem_search: list[str]
