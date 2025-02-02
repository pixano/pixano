# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from enum import Enum

from pixano.features.schemas.source import Source

from .annotations import Annotation
from .base_schema import BaseSchema
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
    SOURCE = "source"

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
    SchemaGroup.SOURCE: Source,
}


def schema_to_group(schema_type: BaseSchema | type) -> SchemaGroup:
    """Get the schema group of a given schema type."""
    try:
        issubclass(schema_type, BaseSchema)
    except TypeError:
        is_class = False
    else:
        is_class = True
    if isinstance(schema_type, Embedding) or is_class and issubclass(schema_type, Embedding):
        return SchemaGroup.EMBEDDING
    elif isinstance(schema_type, Item) or is_class and issubclass(schema_type, Item):
        return SchemaGroup.ITEM
    elif isinstance(schema_type, Entity) or is_class and issubclass(schema_type, Entity):
        return SchemaGroup.ENTITY
    elif isinstance(schema_type, Annotation) or is_class and issubclass(schema_type, Annotation):
        return SchemaGroup.ANNOTATION
    elif isinstance(schema_type, View) or is_class and issubclass(schema_type, View):
        return SchemaGroup.VIEW
    elif isinstance(schema_type, Source) or is_class and issubclass(schema_type, Source):
        return SchemaGroup.SOURCE
    else:
        raise ValueError(f"Unknown schema type: {schema_type}")


def group_to_str(group: SchemaGroup, plural: bool = False) -> str:
    """Convert the schema group to a string.

    Attributes:
        group: The schema group.
        plural: Whether to use the plural form of the word.

    Returns:
        The string for the given schema group.
    """
    if group == SchemaGroup.SOURCE:
        return "sources" if plural else "source"
    elif group == SchemaGroup.ITEM:
        return "items" if plural else "item"
    elif group == SchemaGroup.ENTITY:
        return "entities" if plural else "entity"
    elif group == SchemaGroup.VIEW:
        return "views" if plural else "view"
    elif group == SchemaGroup.ANNOTATION:
        return "annotations" if plural else "annotation"
    elif group == SchemaGroup.EMBEDDING:
        return "embeddings" if plural else "embedding"
    raise ValueError(f"Unknown schema group: {group}")
