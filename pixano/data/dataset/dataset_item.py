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


from typing import Type
from pydantic import BaseModel, create_model
from pixano.core.types.group import TableGroup, TABLE_GROUP_TYPE_DICT


DatasetItem: Type[BaseModel] = create_model(
    "DatasetItem",
    id = (str, ...),
    **{
        table_group.value: (dict[str, TABLE_GROUP_TYPE_DICT[table_group]], None)
        for table_group in TableGroup
    }
)
DatasetItem.__doc__ = "DatasetItem"