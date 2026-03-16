"""Lean API transport models derived from canonical Pixano schemas."""

from pathlib import Path
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field, create_model, field_serializer

from pixano.datasets import Dataset, DatasetFeaturesValues, DatasetInfo
from pixano.datasets.dataset_schema import _serialize_table_schema
from pixano.schemas import (
    BBox,
    CompressedRLE,
    Embedding,
    Entity,
    EntityDynamicState,
    Record,
    KeyPoints,
    Message,
    MultiPath,
    TextSpan,
    Tracklet,
)
from lancedb.pydantic import LanceModel


T = TypeVar("T")


class TransportModel(BaseModel):
    """Base class for API request models."""

    model_config = ConfigDict(extra="allow")


class ResponseModel(BaseModel):
    """Base class for API response models."""

    model_config = ConfigDict(extra="allow", from_attributes=True)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T]
    total: int
    limit: int
    offset: int


def _field_definition(field_name: str, schema: type[LanceModel], optional: bool) -> tuple[Any, Any]:
    field = schema.model_fields[field_name]
    annotation = field.annotation | None if optional else field.annotation

    if optional:
        return annotation, None
    if field.default_factory is not None:
        return annotation, Field(default_factory=field.default_factory)
    if field.is_required():
        return annotation, ...
    return annotation, field.default


def _create_transport_model(
    name: str,
    schema: type[LanceModel],
    *,
    exclude_fields: set[str] | frozenset[str] = frozenset(),
    required_fields: set[str] | frozenset[str] = frozenset(),
    optional: bool = False,
) -> type[BaseModel]:
    field_definitions: dict[str, tuple[Any, Any]] = {}
    for field_name in schema.model_fields:
        if field_name in exclude_fields:
            continue
        if field_name in required_fields:
            field = schema.model_fields[field_name]
            field_definitions[field_name] = (field.annotation, ...)
            continue
        field_definitions[field_name] = _field_definition(field_name, schema, optional)

    base_class = ResponseModel if optional is False and name.endswith("Response") else TransportModel
    return create_model(name, __base__=base_class, **field_definitions)


def serialize_row(
    row: LanceModel,
    *,
    exclude_fields: set[str] | frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Convert a Lance row to a flat API payload."""

    payload: dict[str, Any] = {}
    for key, value in row.model_dump(exclude=set(exclude_fields)).items():
        if isinstance(value, bytes):
            continue
        payload[key] = value
    return payload


def merge_update_payload(existing_row: LanceModel, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial update payload onto an existing row dump."""

    merged = existing_row.model_dump()
    for key, value in patch.items():
        if value is None:
            continue
        merged[key] = value
    return merged


RecordCreate = _create_transport_model(
    "RecordCreate",
    Record,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
RecordUpdate = _create_transport_model(
    "RecordUpdate",
    Record,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
RecordResponse = _create_transport_model("RecordResponse", Record)


class PreviewDescriptor(ResponseModel):
    resource: str
    id: str
    kind: str
    preview_url: str


class RecordListResponse(RecordResponse):
    view_previews: dict[str, PreviewDescriptor] | None = None


EntityCreate = _create_transport_model(
    "EntityCreate",
    Entity,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
EntityUpdate = _create_transport_model(
    "EntityUpdate",
    Entity,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
EntityResponse = _create_transport_model("EntityResponse", Entity)

EntityDynamicStateCreate = _create_transport_model(
    "EntityDynamicStateCreate",
    EntityDynamicState,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
EntityDynamicStateUpdate = _create_transport_model(
    "EntityDynamicStateUpdate",
    EntityDynamicState,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
EntityDynamicStateResponse = _create_transport_model("EntityDynamicStateResponse", EntityDynamicState)


class ImageResponse(ResponseModel):
    id: str
    record_id: str
    logical_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    src: str


class TextResponse(ResponseModel):
    id: str
    record_id: str
    logical_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    content: str = ""
    uri: str = ""


class SFrameResponse(ResponseModel):
    id: str
    record_id: str
    logical_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    timestamp: float = 0
    frame_index: int = 0
    src: str


TrackletCreate = _create_transport_model(
    "TrackletCreate",
    Tracklet,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
TrackletUpdate = _create_transport_model(
    "TrackletUpdate",
    Tracklet,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
TrackletResponse = _create_transport_model("TrackletResponse", Tracklet)

BBoxCreate = _create_transport_model(
    "BBoxCreate",
    BBox,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
BBoxUpdate = _create_transport_model(
    "BBoxUpdate",
    BBox,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
BBoxResponse = _create_transport_model("BBoxResponse", BBox)

MaskCreate = _create_transport_model(
    "MaskCreate",
    CompressedRLE,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
MaskUpdate = _create_transport_model(
    "MaskUpdate",
    CompressedRLE,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
MaskResponse = _create_transport_model("MaskResponse", CompressedRLE)

MultiPathCreate = _create_transport_model(
    "MultiPathCreate",
    MultiPath,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
MultiPathUpdate = _create_transport_model(
    "MultiPathUpdate",
    MultiPath,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
MultiPathResponse = _create_transport_model("MultiPathResponse", MultiPath)

KeyPointsCreate = _create_transport_model(
    "KeyPointsCreate",
    KeyPoints,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
KeyPointsUpdate = _create_transport_model(
    "KeyPointsUpdate",
    KeyPoints,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
KeyPointsResponse = _create_transport_model("KeyPointsResponse", KeyPoints)

TextSpanCreate = _create_transport_model(
    "TextSpanCreate",
    TextSpan,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
TextSpanUpdate = _create_transport_model(
    "TextSpanUpdate",
    TextSpan,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
TextSpanResponse = _create_transport_model("TextSpanResponse", TextSpan)

MessageCreate = _create_transport_model(
    "MessageCreate",
    Message,
    exclude_fields={"created_at", "updated_at"},
    required_fields={"id"},
)
MessageUpdate = _create_transport_model(
    "MessageUpdate",
    Message,
    exclude_fields={"id", "created_at", "updated_at"},
    optional=True,
)
MessageResponse = _create_transport_model("MessageResponse", Message)


class ConversationResponse(BaseModel):
    """Read-only conversation aggregate returned by the API."""

    conversation_id: str
    messages: list[MessageResponse]


EmbeddingCreate = _create_transport_model(
    "EmbeddingCreate",
    Embedding,
    exclude_fields={"created_at", "updated_at", "vector"},
    required_fields={"id"},
)
EmbeddingResponse = _create_transport_model("EmbeddingResponse", Embedding, exclude_fields={"vector"})


class DatasetInfoResponse(DatasetInfo):
    """Dataset info plus the number of records."""

    num_records: int

    @field_serializer(
        "record",
        "entity",
        "entity_dynamic_state",
        "bbox",
        "mask",
        "multi_path",
        "keypoint",
        "tracklet",
        "message",
        "text_span",
        when_used="json",
    )
    def serialize_schema_slot(self, schema_cls: type[LanceModel] | None) -> dict[str, Any] | None:
        """Serialize schema slots to JSON-friendly payloads."""

        return _serialize_table_schema(schema_cls) if schema_cls is not None else None

    @field_serializer("views", when_used="json")
    def serialize_views(self, views: dict[str, type[LanceModel]]) -> dict[str, dict[str, Any]]:
        """Serialize logical views to JSON-friendly payloads."""

        return {logical_name: _serialize_table_schema(schema_cls) for logical_name, schema_cls in views.items()}

    @classmethod
    def from_dataset_info(cls, info: DatasetInfo, dataset_dir: Path) -> "DatasetInfoResponse":
        dataset = Dataset(dataset_dir)
        num_records = dataset.num_rows
        return cls(num_records=num_records, **info.model_dump(exclude={"tables"}))


class DatasetResponse(BaseModel):
    """Full dataset metadata returned by dataset endpoints."""

    id: str
    path: Path
    previews_path: Path
    thumbnail: Path
    tables: dict[str, Any]
    feature_values: DatasetFeaturesValues
    info: DatasetInfoResponse

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "DatasetResponse":
        tables = {name: schema.__name__ for name, schema in dataset.info.tables.items()}
        return cls(
            id=dataset.info.id,
            path=dataset.path,
            previews_path=dataset.previews_path,
            thumbnail=dataset.thumbnail,
            tables=tables,
            feature_values=dataset.features_values,
            info=DatasetInfoResponse.from_dataset_info(dataset.info, dataset.path),
        )


__all__ = [
    "BBoxCreate",
    "BBoxResponse",
    "BBoxUpdate",
    "DatasetInfoResponse",
    "DatasetResponse",
    "EmbeddingCreate",
    "EmbeddingResponse",
    "EntityCreate",
    "EntityDynamicStateCreate",
    "EntityDynamicStateResponse",
    "EntityDynamicStateUpdate",
    "EntityResponse",
    "EntityUpdate",
    "RecordCreate",
    "RecordResponse",
    "RecordUpdate",
    "KeyPointsCreate",
    "KeyPointsResponse",
    "KeyPointsUpdate",
    "MaskCreate",
    "MaskResponse",
    "MaskUpdate",
    "MultiPathCreate",
    "MultiPathResponse",
    "MultiPathUpdate",
    "ConversationResponse",
    "MessageCreate",
    "MessageResponse",
    "MessageUpdate",
    "PaginatedResponse",
    "ImageResponse",
    "SFrameResponse",
    "TextResponse",
    "TextSpanCreate",
    "TextSpanResponse",
    "TextSpanUpdate",
    "TrackletCreate",
    "TrackletResponse",
    "TrackletUpdate",
    "TransportModel",
    "merge_update_payload",
    "serialize_row",
]
