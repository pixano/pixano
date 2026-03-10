from __future__ import annotations

import re

from lancedb.pydantic import LanceModel

from .annotations import (
    BBox,
    CompressedRLE,
    KeyPoints,
    Message,
    TextSpan,
    Tracklet,
    is_bbox,
    is_compressed_rle,
    is_keypoints,
    is_message,
    is_text_span,
    is_tracklet,
)
from .entities import Entity, EntityDynamicState, is_entity, is_entity_dynamic_state
from .records import Record, is_record
from .views import Image, PDF, SequenceFrame, Text, View, is_pdf, is_sequence_frame, is_text, is_view

_SLOT_TO_TABLE: dict[str, str] = {
    "record": "records",
    "entity": "entities",
    "entity_dynamic_state": "entity_dynamic_states",
    "bbox": "bboxes",
    "mask": "masks",
    "keypoint": "keypoints",
    "tracklet": "tracklets",
    "message": "messages",
    "text_span": "text_spans",
}


def supported_dataset_info_slots() -> tuple[str, ...]:
    return tuple(_SLOT_TO_TABLE)


def canonical_table_name_for_slot(slot_name: str) -> str:
    try:
        return _SLOT_TO_TABLE[slot_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported DatasetInfo slot '{slot_name}'.") from exc


def _camel_to_snake(name: str) -> str:
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def _pluralize(snake_name: str) -> str:
    if snake_name.endswith("y") and len(snake_name) > 1 and snake_name[-2] not in "aeiou":
        return f"{snake_name[:-1]}ies"
    if snake_name.endswith(("s", "x", "z", "ch", "sh")):
        return f"{snake_name}es"
    return f"{snake_name}s"


def canonical_table_name_for_view_schema(schema_cls: type[View]) -> str:
    if not (isinstance(schema_cls, type) and issubclass(schema_cls, View)):
        raise ValueError(f"Expected a View subclass, got {schema_cls}.")
    return _pluralize(_camel_to_snake(schema_cls.__name__))


def canonical_table_name_for_schema(schema_cls: type[LanceModel]) -> str:
    if is_record(schema_cls):
        return canonical_table_name_for_slot("record")
    if is_entity(schema_cls):
        return canonical_table_name_for_slot("entity")
    if is_entity_dynamic_state(schema_cls):
        return canonical_table_name_for_slot("entity_dynamic_state")
    if is_bbox(schema_cls):
        return canonical_table_name_for_slot("bbox")
    if is_compressed_rle(schema_cls):
        return canonical_table_name_for_slot("mask")
    if is_keypoints(schema_cls):
        return canonical_table_name_for_slot("keypoint")
    if is_tracklet(schema_cls):
        return canonical_table_name_for_slot("tracklet")
    if is_message(schema_cls):
        return canonical_table_name_for_slot("message")
    if is_text_span(schema_cls):
        return canonical_table_name_for_slot("text_span")
    if is_view(schema_cls):
        return canonical_table_name_for_view_schema(schema_cls)
    raise ValueError(f"Unsupported schema type for canonical table resolution: {schema_cls}.")


def is_supported_view_schema(schema_cls: type[LanceModel]) -> bool:
    return any(
        isinstance(schema_cls, type) and issubclass(schema_cls, base) for base in (Image, SequenceFrame, Text, PDF)
    )


def supported_slot_schema(slot_name: str) -> type[LanceModel]:
    mapping: dict[str, type[LanceModel]] = {
        "record": Record,
        "entity": Entity,
        "entity_dynamic_state": EntityDynamicState,
        "bbox": BBox,
        "mask": CompressedRLE,
        "keypoint": KeyPoints,
        "tracklet": Tracklet,
        "message": Message,
        "text_span": TextSpan,
    }
    try:
        return mapping[slot_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported DatasetInfo slot '{slot_name}'.") from exc
