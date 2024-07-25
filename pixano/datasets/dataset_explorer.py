# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any

from pydantic import BaseModel


class ColDesc(BaseModel):
    """Column description.

    Attributes:
        name (str): column name
        type (str): column type
    """

    name: str
    type: str


class TableData(BaseModel):
    """Table data.

    Attributes:
        col (list[ColDesc]): column descriptions
        rows (list[dict[str, Any]]): rows (actual data)
    """

    cols: list[ColDesc]
    rows: list[dict[str, Any]]
    # Note: Any is one of the allowed cell types (int, float, str, bool, Image/Video/..., graph, ...)


class PaginationInfo(BaseModel):
    """Pagination info.

    Attributes:
        current (int): current page
        size (int): number of items per page
        total (int): total number of items
    """

    current: int
    size: int
    total: int


class DatasetExplorer(BaseModel):
    """Data for Dataset Explorer page.

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
