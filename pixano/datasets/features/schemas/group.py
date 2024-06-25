# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

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
