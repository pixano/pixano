# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from enum import Enum

from .annotations import Annotation
from .embeddings import Embedding
from .entities import Entity
from .items import Item
from .views import View


class _SchemaGroup(Enum):
    """Schema group."""

    ANNOTATION = "annotations"
    EMBEDDING = "embeddings"
    ITEM = "item"
    ENTITY = "entities"
    VIEW = "views"

    @classmethod
    def _missing_(cls, name):
        for member in cls:
            if member.value == name.lower():
                return member


_SCHEMA_GROUP_TO_SCHEMA_DICT = {
    _SchemaGroup.EMBEDDING: Embedding,
    _SchemaGroup.ITEM: Item,
    _SchemaGroup.ENTITY: Entity,
    _SchemaGroup.ANNOTATION: Annotation,
    _SchemaGroup.VIEW: View,
}
