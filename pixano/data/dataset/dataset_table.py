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


from typing import Optional

from pydantic import BaseModel


class DatasetTable(BaseModel):
    """DatasetTable

    Attributes:
        name (str): Table name
        fields (dict[str, str]): Table fields
        source (str, optional): Table source
        type (str, optional): Table type
    """

    name: str
    fields: dict[str, str]
    source: Optional[str] = None
    type: Optional[str] = None
