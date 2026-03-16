# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

from dataclasses import dataclass

from lancedb.pydantic import LanceModel

from .annotations import BBox, CompressedRLE, KeyPoints, Message, TextSpan, Tracklet
from .embeddings import Embedding
from .entities import Entity, EntityDynamicState
from .records import Record
from .schema_group import SchemaGroup
from .views import PDF, Image, PointCloud, SequenceFrame, Text, Video, View


@dataclass(frozen=True, slots=True)
class CanonicalResourceFamily:
    """Descriptor for one canonical resource family in the dataset schema."""

    slot_name: str
    resource_name: str
    table_name: str
    schema_group: SchemaGroup
    base_schema: type[LanceModel]
    public_api: bool = True
    unique_per_dataset: bool = True


_CANONICAL_RESOURCE_FAMILIES: tuple[CanonicalResourceFamily, ...] = (
    CanonicalResourceFamily("record", "records", "records", SchemaGroup.RECORD, Record),
    CanonicalResourceFamily("entity", "entities", "entities", SchemaGroup.ENTITY, Entity),
    CanonicalResourceFamily(
        "entity_dynamic_state",
        "entity-dynamic-states",
        "entity_dynamic_states",
        SchemaGroup.ENTITY_DYNAMIC_STATE,
        EntityDynamicState,
    ),
    CanonicalResourceFamily("bbox", "bboxes", "bboxes", SchemaGroup.ANNOTATION, BBox),
    CanonicalResourceFamily("mask", "masks", "masks", SchemaGroup.ANNOTATION, CompressedRLE),
    CanonicalResourceFamily("keypoint", "keypoints", "keypoints", SchemaGroup.ANNOTATION, KeyPoints),
    CanonicalResourceFamily("tracklet", "tracklets", "tracklets", SchemaGroup.ANNOTATION, Tracklet),
    CanonicalResourceFamily("message", "messages", "messages", SchemaGroup.ANNOTATION, Message),
    CanonicalResourceFamily("text_span", "text-spans", "text_spans", SchemaGroup.ANNOTATION, TextSpan),
    CanonicalResourceFamily("image", "images", "images", SchemaGroup.VIEW, Image),
    CanonicalResourceFamily(
        "sequence_frame",
        "sframes",
        "sequence_frames",
        SchemaGroup.VIEW,
        SequenceFrame,
    ),
    CanonicalResourceFamily("text", "texts", "texts", SchemaGroup.VIEW, Text),
    CanonicalResourceFamily("video", "videos", "videos", SchemaGroup.VIEW, Video),
    CanonicalResourceFamily("point_cloud", "point-clouds", "point_clouds", SchemaGroup.VIEW, PointCloud),
    CanonicalResourceFamily("pdf", "pdfs", "pdfs", SchemaGroup.VIEW, PDF, public_api=False),
    CanonicalResourceFamily("embedding", "embeddings", "embeddings", SchemaGroup.EMBEDDING, Embedding),
)

_SLOT_TO_FAMILY = {family.slot_name: family for family in _CANONICAL_RESOURCE_FAMILIES}
_RESOURCE_TO_FAMILY = {family.resource_name: family for family in _CANONICAL_RESOURCE_FAMILIES}


def public_resource_families() -> tuple[CanonicalResourceFamily, ...]:
    """Return all resource families exposed through the public API."""
    return tuple(family for family in _CANONICAL_RESOURCE_FAMILIES if family.public_api)


def supported_dataset_info_slots() -> tuple[str, ...]:
    """Return slot names that are supported in DatasetInfo."""
    return tuple(
        family.slot_name
        for family in _CANONICAL_RESOURCE_FAMILIES
        if family.slot_name
        in {
            "record",
            "entity",
            "entity_dynamic_state",
            "bbox",
            "mask",
            "keypoint",
            "tracklet",
            "message",
            "text_span",
        }
    )


def canonical_family_spec_for_slot(slot_name: str) -> CanonicalResourceFamily:
    """Look up a resource family by its DatasetInfo slot name."""
    try:
        return _SLOT_TO_FAMILY[slot_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported DatasetInfo slot '{slot_name}'.") from exc


def canonical_family_spec_for_resource(resource_name: str) -> CanonicalResourceFamily:
    """Look up a resource family by its API resource name."""
    try:
        return _RESOURCE_TO_FAMILY[resource_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported resource family '{resource_name}'.") from exc


def canonical_base_schema_for_schema(schema_cls: type[LanceModel]) -> type[LanceModel]:
    """Return the canonical base schema for the given schema class."""
    if not isinstance(schema_cls, type) or not issubclass(schema_cls, LanceModel):
        raise ValueError(f"Unsupported schema type for canonical family resolution: {schema_cls}.")

    families_by_base = {family.base_schema: family for family in _CANONICAL_RESOURCE_FAMILIES}
    for base_schema in schema_cls.__mro__:
        if base_schema in families_by_base:
            return base_schema

    if issubclass(schema_cls, View):
        raise ValueError(f"Unsupported view schema for canonical family resolution: {schema_cls}.")
    raise ValueError(f"Unsupported schema type for canonical family resolution: {schema_cls}.")


def canonical_family_spec_for_schema(schema_cls: type[LanceModel]) -> CanonicalResourceFamily:
    """Look up a resource family by its schema class."""
    base_schema = canonical_base_schema_for_schema(schema_cls)
    for family in _CANONICAL_RESOURCE_FAMILIES:
        if family.base_schema is base_schema:
            return family
    raise ValueError(f"Unsupported schema type for canonical family resolution: {schema_cls}.")


def canonical_table_name_for_slot(slot_name: str) -> str:
    """Return the canonical table name for a DatasetInfo slot."""
    return canonical_family_spec_for_slot(slot_name).table_name


def canonical_table_name_for_schema(schema_cls: type[LanceModel]) -> str:
    """Return the canonical table name for the given schema class."""
    return canonical_family_spec_for_schema(schema_cls).table_name


def canonical_table_name_for_view_schema(schema_cls: type[View]) -> str:
    """Return the canonical table name for a View schema class."""
    return canonical_table_name_for_schema(schema_cls)


def canonical_resource_name_for_schema(schema_cls: type[LanceModel]) -> str:
    """Return the canonical API resource name for the given schema class."""
    return canonical_family_spec_for_schema(schema_cls).resource_name


def is_supported_view_schema(schema_cls: type[LanceModel]) -> bool:
    """Check whether a schema class is a supported view schema."""
    try:
        family = canonical_family_spec_for_schema(schema_cls)
    except ValueError:
        return False
    return family.schema_group == SchemaGroup.VIEW


def supported_slot_schema(slot_name: str) -> type[LanceModel]:
    """Return the base schema class for the given DatasetInfo slot name."""
    return canonical_family_spec_for_slot(slot_name).base_schema


def validate_canonical_table_map(tables: dict[str, type[LanceModel]]) -> None:
    """Validate that all table names and schema classes are canonical and unique."""
    families_seen: dict[type[LanceModel], str] = {}

    for table_name, schema_cls in tables.items():
        family = canonical_family_spec_for_schema(schema_cls)
        expected_table = family.table_name
        if table_name != expected_table:
            raise ValueError(
                f"Invalid dataset schema: table '{table_name}' for {schema_cls.__name__} must use canonical name "
                f"'{expected_table}'."
            )
        previous_table = families_seen.get(family.base_schema)
        if previous_table is not None and previous_table != table_name:
            raise ValueError(
                f"Invalid dataset schema: multiple tables found for {family.base_schema.__name__}: "
                f"['{previous_table}', '{table_name}']."
            )
        families_seen[family.base_schema] = table_name


__all__ = [
    "CanonicalResourceFamily",
    "canonical_base_schema_for_schema",
    "canonical_family_spec_for_resource",
    "canonical_family_spec_for_schema",
    "canonical_family_spec_for_slot",
    "canonical_resource_name_for_schema",
    "canonical_table_name_for_schema",
    "canonical_table_name_for_slot",
    "canonical_table_name_for_view_schema",
    "is_supported_view_schema",
    "public_resource_families",
    "supported_dataset_info_slots",
    "supported_slot_schema",
    "validate_canonical_table_map",
]
