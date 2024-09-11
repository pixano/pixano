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


class SchemaGroup(Enum):
    """Schema group.

    It defines the different schema groups to which a schema can belong.

    Attributes:
        ANNOTATION: Annotation schema group.
        EMBEDDING: Embedding schema group.
        ITEM: Item schema group.
        ENTITY: Entity schema group.
        VIEW: View schema group.
    """

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
    SchemaGroup.EMBEDDING: Embedding,
    SchemaGroup.ITEM: Item,
    SchemaGroup.ENTITY: Entity,
    SchemaGroup.ANNOTATION: Annotation,
    SchemaGroup.VIEW: View,
}
