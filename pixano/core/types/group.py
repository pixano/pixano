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


from enum import Enum
from .view import View
from .object import Object
from .item import Item
from .embedding import Embedding


class TableGroup(Enum):
    ITEM = "item"
    VIEW = "views"
    OBJECT = "objects"
    EMBEDDING = "embeddings"


TABLE_GROUP_TYPE_DICT = {
    TableGroup.ITEM: Item,
    TableGroup.VIEW: View,
    TableGroup.OBJECT: Object,
    TableGroup.EMBEDDING: Embedding
}
