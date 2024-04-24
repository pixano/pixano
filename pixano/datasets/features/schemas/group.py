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

from .embedding import Embedding
from .item import Item
from .object import Object
from .tracklet import Tracklet
from .view import View


class _SchemaGroup(Enum):
    """Schema group."""

    EMBEDDING = "embeddings"
    ITEM = "item"
    OBJECT = "objects"
    TRACKLET = "tracklets"
    VIEW = "views"

    @classmethod
    def _missing_(cls, name):
        for member in cls:
            if member.value == name.lower():
                return member


_SCHEMA_GROUP_TO_SCHEMA_DICT = {
    _SchemaGroup.EMBEDDING: Embedding,
    _SchemaGroup.ITEM: Item,
    _SchemaGroup.OBJECT: Object,
    _SchemaGroup.TRACKLET: Tracklet,
    _SchemaGroup.VIEW: View,
}
