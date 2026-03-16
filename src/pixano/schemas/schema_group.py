# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from enum import Enum

from lancedb.pydantic import LanceModel

from .annotations import (
    BBox,
    BBox3D,
    Classification,
    CompressedRLE,
    EntityAnnotation,
    EntityGroupAnnotation,
    KeyPoints,
    KeyPoints3D,
    Message,
    MultiPath,
    Relation,
    TextSpan,
    Tracklet,
)
from .embeddings import Embedding, ViewEmbedding
from .entities import Entity, EntityDynamicState
from .records import Record
from .views import PDF, CamCalibration, Image, PointCloud, PointCloudFrame, SequenceFrame, Text, Video, View


class SchemaGroup(Enum):
    """High-level groups used by datasets and the API layer."""

    ANNOTATION = "annotations"
    EMBEDDING = "embeddings"
    RECORD = "records"
    ENTITY = "entities"
    ENTITY_DYNAMIC_STATE = "entity_dynamic_states"
    VIEW = "views"

    @classmethod
    def _missing_(cls, name: object):
        if isinstance(name, str):
            for member in cls:
                if member.value == name.lower():
                    return member
        return None


_SCHEMA_GROUP_TO_SCHEMA_DICT = {
    SchemaGroup.EMBEDDING: Embedding,
    SchemaGroup.RECORD: Record,
    SchemaGroup.ENTITY: Entity,
    SchemaGroup.ENTITY_DYNAMIC_STATE: EntityDynamicState,
    SchemaGroup.ANNOTATION: EntityAnnotation,
    SchemaGroup.VIEW: View,
}

CANONICAL_SCHEMA_TYPES = (
    Record,
    View,
    CamCalibration,
    Image,
    PDF,
    PointCloud,
    PointCloudFrame,
    SequenceFrame,
    Text,
    Video,
    Entity,
    EntityDynamicState,
    EntityAnnotation,
    EntityGroupAnnotation,
    BBox,
    BBox3D,
    Classification,
    CompressedRLE,
    KeyPoints,
    KeyPoints3D,
    Message,
    MultiPath,
    Relation,
    TextSpan,
    Tracklet,
    Embedding,
    ViewEmbedding,
)

CANONICAL_SCHEMA_MAP: dict[str, type[LanceModel]] = {
    schema_type.__name__: schema_type for schema_type in CANONICAL_SCHEMA_TYPES
}


def schema_to_group(schema_type: LanceModel | type) -> SchemaGroup:
    """Get the schema group of a given schema type."""
    try:
        is_class = issubclass(schema_type, LanceModel)
    except TypeError:
        is_class = False

    if isinstance(schema_type, Embedding) or is_class and issubclass(schema_type, Embedding):
        return SchemaGroup.EMBEDDING
    if isinstance(schema_type, Record) or is_class and issubclass(schema_type, Record):
        return SchemaGroup.RECORD
    if isinstance(schema_type, EntityDynamicState) or is_class and issubclass(schema_type, EntityDynamicState):
        return SchemaGroup.ENTITY_DYNAMIC_STATE
    if isinstance(schema_type, Entity) or is_class and issubclass(schema_type, Entity):
        return SchemaGroup.ENTITY
    # Check EntityAnnotation and EntityGroupAnnotation (both are annotation groups)
    if (
        isinstance(schema_type, (EntityAnnotation, EntityGroupAnnotation))
        or is_class
        and (issubclass(schema_type, EntityAnnotation) or issubclass(schema_type, EntityGroupAnnotation))
    ):
        return SchemaGroup.ANNOTATION
    if isinstance(schema_type, View) or is_class and issubclass(schema_type, View):
        return SchemaGroup.VIEW
    raise ValueError(f"Unknown schema type: {schema_type}")


def group_to_str(group: SchemaGroup, plural: bool = False) -> str:
    """Convert a schema group to its API/storage string."""
    if group == SchemaGroup.RECORD:
        return "records" if plural else "record"
    if group == SchemaGroup.ENTITY:
        return "entities" if plural else "entity"
    if group == SchemaGroup.ENTITY_DYNAMIC_STATE:
        return "entity_dynamic_states" if plural else "entity_dynamic_state"
    if group == SchemaGroup.VIEW:
        return "views" if plural else "view"
    if group == SchemaGroup.ANNOTATION:
        return "annotations" if plural else "annotation"
    if group == SchemaGroup.EMBEDDING:
        return "embeddings" if plural else "embedding"
    raise ValueError(f"Unknown schema group: {group}")
