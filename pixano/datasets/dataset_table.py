# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel


########### TODO : to delete, unused ?  ############


class DatasetTable(BaseModel):
    """DatasetTable.

    Attributes:
        name (str): Table name
        fields (dict[str, str]): Table fields
        source (str, optional): Table source
        type (str, optional): Table type
    """

    name: str
    fields: dict[str, str]
    source: str | None = None
    type: str | None = None
