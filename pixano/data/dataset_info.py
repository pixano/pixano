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

from typing import Any, Optional

from pydantic import BaseModel

from pixano.data.fields import Fields


class DatasetInfo(BaseModel):
    """DatasetInfo

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        num_elements (int): Number of elements in dataset
        fields (Fields, optional): Dataset fields
        preview (str, optional): Dataset preview
        categories (list[dict], optional): Dataset categories
        model_id (str, optional): Model ID
        model_name (str, optional): Model name
        model_description (str, optional): Model description
    """

    id: str
    name: str
    description: str
    fields: Optional[Fields]
    num_elements: Optional[int]
    preview: Optional[str]
    categories: Optional[list[dict]]
    model_id: Optional[str]
    model_name: Optional[str]
    model_description: Optional[str]

    class Config:
        arbitrary_types_allowed = True

    def to_dict(self) -> dict[str, Any]:
        def _value_as_dict(value):
            if isinstance(value, Fields):
                return value.to_dict()
            else:
                return value

        return {attr: _value_as_dict(getattr(self, attr)) for attr in vars(self).keys()}
