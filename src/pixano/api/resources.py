# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Canonical API resource definitions."""

from dataclasses import dataclass
from typing import Any, Callable

from lancedb.pydantic import LanceModel
from pydantic import BaseModel

from pixano.schemas import (
    BBox,
    CompressedRLE,
    Embedding,
    Entity,
    EntityDynamicState,
    KeyPoints,
    Message,
    MultiPath,
    Record,
    SchemaGroup,
    TextSpan,
    Tracklet,
    canonical_table_name_for_schema,
)

from .models import (
    BBoxCreate,
    BBoxResponse,
    BBoxUpdate,
    EmbeddingCreate,
    EmbeddingResponse,
    EntityCreate,
    EntityDynamicStateCreate,
    EntityDynamicStateResponse,
    EntityDynamicStateUpdate,
    EntityResponse,
    EntityUpdate,
    KeyPointsCreate,
    KeyPointsResponse,
    KeyPointsUpdate,
    MaskCreate,
    MaskResponse,
    MaskUpdate,
    MessageCreate,
    MessageResponse,
    MessageUpdate,
    MultiPathCreate,
    MultiPathResponse,
    MultiPathUpdate,
    RecordCreate,
    RecordResponse,
    RecordUpdate,
    TextSpanCreate,
    TextSpanResponse,
    TextSpanUpdate,
    TrackletCreate,
    TrackletResponse,
    TrackletUpdate,
)


CreateValidator = Callable[[Any, dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """Static API metadata for one resource family."""

    name: str
    path: str
    tag: str
    schema_group: SchemaGroup
    schema_cls: type[LanceModel]
    canonical_table_name: str
    response_model: type[BaseModel]
    create_model: type[BaseModel] | None = None
    update_model: type[BaseModel] | None = None
    response_exclude_fields: frozenset[str] = frozenset()
    list_filters: tuple[str, ...] = ("where",)
    allow_create: bool = True
    allow_update: bool = True
    allow_delete: bool = True
    validate_create: CreateValidator | None = None


def _validate_entity_create(service: Any, data: dict[str, Any]) -> None:
    service.validate_record_exists(data["record_id"])
    parent_id = data.get("parent_id", "")
    if parent_id:
        service.validate_entity_exists(parent_id)


def _validate_tracklet_create(service: Any, data: dict[str, Any]) -> None:
    service.validate_record_exists(data["record_id"])
    service.validate_entity_exists(data["entity_id"])


def _validate_per_frame_annotation_create(service: Any, data: dict[str, Any]) -> None:
    service.validate_record_exists(data["record_id"])
    entity_id = data["entity_id"]
    service.validate_entity_exists(entity_id)

    tracklet_id = data.get("tracklet_id", "")
    if tracklet_id:
        service.validate_tracklet_exists(tracklet_id, expected_entity_id=entity_id)

    entity_dynamic_state_id = data.get("entity_dynamic_state_id", "")
    if entity_dynamic_state_id:
        service.validate_eds_exists(entity_dynamic_state_id, expected_entity_id=entity_id)


def _validate_entity_dynamic_state_create(service: Any, data: dict[str, Any]) -> None:
    service.validate_record_exists(data["record_id"])
    service.validate_entity_exists(data["entity_id"])

    tracklet_id = data.get("tracklet_id", "")
    if tracklet_id:
        service.validate_tracklet_exists(tracklet_id, expected_entity_id=data["entity_id"])


def _validate_text_span_create(service: Any, data: dict[str, Any]) -> None:
    service.validate_record_exists(data["record_id"])
    service.validate_entity_exists(data["entity_id"])


def _validate_message_create(service: Any, data: dict[str, Any]) -> None:
    service.validate_record_exists(data["record_id"])

    entity_id = data.get("entity_id", "")
    if entity_id:
        service.validate_entity_exists(entity_id)

    for referenced_entity_id in data.get("entity_ids", []):
        service.validate_entity_exists(referenced_entity_id)


RECORD_RESOURCE = ResourceSpec(
    name="record",
    path="records",
    tag="Records",
    schema_group=SchemaGroup.RECORD,
    schema_cls=Record,
    canonical_table_name=canonical_table_name_for_schema(Record),
    create_model=RecordCreate,
    update_model=RecordUpdate,
    response_model=RecordResponse,
)

ENTITY_RESOURCE = ResourceSpec(
    name="entity",
    path="entities",
    tag="Entities",
    schema_group=SchemaGroup.ENTITY,
    schema_cls=Entity,
    canonical_table_name=canonical_table_name_for_schema(Entity),
    create_model=EntityCreate,
    update_model=EntityUpdate,
    response_model=EntityResponse,
    list_filters=("record_id", "where"),
    validate_create=_validate_entity_create,
)

ENTITY_DYNAMIC_STATE_RESOURCE = ResourceSpec(
    name="entity_dynamic_state",
    path="entity-dynamic-states",
    tag="Entity Dynamic States",
    schema_group=SchemaGroup.ENTITY_DYNAMIC_STATE,
    schema_cls=EntityDynamicState,
    canonical_table_name=canonical_table_name_for_schema(EntityDynamicState),
    create_model=EntityDynamicStateCreate,
    update_model=EntityDynamicStateUpdate,
    response_model=EntityDynamicStateResponse,
    list_filters=(
        "record_id",
        "entity_id",
        "view_name",
        "source_type",
        "tracklet_id",
        "frame_index",
        "where",
    ),
    validate_create=_validate_entity_dynamic_state_create,
)

TRACKLET_RESOURCE = ResourceSpec(
    name="tracklet",
    path="tracklets",
    tag="Tracklets",
    schema_group=SchemaGroup.ANNOTATION,
    schema_cls=Tracklet,
    canonical_table_name=canonical_table_name_for_schema(Tracklet),
    create_model=TrackletCreate,
    update_model=TrackletUpdate,
    response_model=TrackletResponse,
    list_filters=("record_id", "entity_id", "view_name", "source_type", "where"),
    validate_create=_validate_tracklet_create,
)

BBOX_RESOURCE = ResourceSpec(
    name="bbox",
    path="bboxes",
    tag="BBoxes",
    schema_group=SchemaGroup.ANNOTATION,
    schema_cls=BBox,
    canonical_table_name=canonical_table_name_for_schema(BBox),
    create_model=BBoxCreate,
    update_model=BBoxUpdate,
    response_model=BBoxResponse,
    list_filters=(
        "record_id",
        "entity_id",
        "view_name",
        "source_type",
        "tracklet_id",
        "frame_index",
        "where",
    ),
    validate_create=_validate_per_frame_annotation_create,
)

MASK_RESOURCE = ResourceSpec(
    name="mask",
    path="masks",
    tag="Masks",
    schema_group=SchemaGroup.ANNOTATION,
    schema_cls=CompressedRLE,
    canonical_table_name=canonical_table_name_for_schema(CompressedRLE),
    create_model=MaskCreate,
    update_model=MaskUpdate,
    response_model=MaskResponse,
    list_filters=(
        "record_id",
        "entity_id",
        "view_name",
        "source_type",
        "tracklet_id",
        "frame_index",
        "where",
    ),
    validate_create=_validate_per_frame_annotation_create,
)

MULTI_PATH_RESOURCE = ResourceSpec(
    name="multi_path",
    path="multi-paths",
    tag="Multi-Paths",
    schema_group=SchemaGroup.ANNOTATION,
    schema_cls=MultiPath,
    canonical_table_name=canonical_table_name_for_schema(MultiPath),
    create_model=MultiPathCreate,
    update_model=MultiPathUpdate,
    response_model=MultiPathResponse,
    list_filters=(
        "record_id",
        "entity_id",
        "view_name",
        "source_type",
        "tracklet_id",
        "frame_index",
        "where",
    ),
    validate_create=_validate_per_frame_annotation_create,
)

KEYPOINTS_RESOURCE = ResourceSpec(
    name="keypoints",
    path="keypoints",
    tag="KeyPoints",
    schema_group=SchemaGroup.ANNOTATION,
    schema_cls=KeyPoints,
    canonical_table_name=canonical_table_name_for_schema(KeyPoints),
    create_model=KeyPointsCreate,
    update_model=KeyPointsUpdate,
    response_model=KeyPointsResponse,
    list_filters=(
        "record_id",
        "entity_id",
        "view_name",
        "source_type",
        "tracklet_id",
        "frame_index",
        "where",
    ),
    validate_create=_validate_per_frame_annotation_create,
)

TEXT_SPAN_RESOURCE = ResourceSpec(
    name="text_span",
    path="text-spans",
    tag="Text Spans",
    schema_group=SchemaGroup.ANNOTATION,
    schema_cls=TextSpan,
    canonical_table_name=canonical_table_name_for_schema(TextSpan),
    create_model=TextSpanCreate,
    update_model=TextSpanUpdate,
    response_model=TextSpanResponse,
    list_filters=("record_id", "entity_id", "view_name", "source_type", "where"),
    validate_create=_validate_text_span_create,
)

MESSAGE_RESOURCE = ResourceSpec(
    name="message",
    path="messages",
    tag="Messages",
    schema_group=SchemaGroup.ANNOTATION,
    schema_cls=Message,
    canonical_table_name=canonical_table_name_for_schema(Message),
    create_model=MessageCreate,
    update_model=MessageUpdate,
    response_model=MessageResponse,
    list_filters=("record_id", "entity_id", "view_name", "source_type", "where"),
    validate_create=_validate_message_create,
)

EMBEDDING_RESOURCE = ResourceSpec(
    name="embedding",
    path="embeddings",
    tag="Embeddings",
    schema_group=SchemaGroup.EMBEDDING,
    schema_cls=Embedding,
    canonical_table_name=canonical_table_name_for_schema(Embedding),
    create_model=EmbeddingCreate,
    response_model=EmbeddingResponse,
    response_exclude_fields=frozenset({"vector"}),
    list_filters=("record_id", "view_name", "where"),
    allow_update=False,
    allow_delete=False,
)

RESOURCE_SPECS: tuple[ResourceSpec, ...] = (
    RECORD_RESOURCE,
    ENTITY_RESOURCE,
    ENTITY_DYNAMIC_STATE_RESOURCE,
    TRACKLET_RESOURCE,
    BBOX_RESOURCE,
    MASK_RESOURCE,
    MULTI_PATH_RESOURCE,
    KEYPOINTS_RESOURCE,
    MESSAGE_RESOURCE,
    TEXT_SPAN_RESOURCE,
    EMBEDDING_RESOURCE,
)


__all__ = [
    "BBOX_RESOURCE",
    "EMBEDDING_RESOURCE",
    "ENTITY_DYNAMIC_STATE_RESOURCE",
    "ENTITY_RESOURCE",
    "RECORD_RESOURCE",
    "KEYPOINTS_RESOURCE",
    "MASK_RESOURCE",
    "MESSAGE_RESOURCE",
    "MULTI_PATH_RESOURCE",
    "ResourceSpec",
    "TEXT_SPAN_RESOURCE",
    "TRACKLET_RESOURCE",
    "RESOURCE_SPECS",
]
