# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping

import shortuuid

from pixano.features.utils.creators import create_instance_of_schema
from pixano.schemas import (
    Entity,
    EntityAnnotation,
    EntityGroupAnnotation,
    Message,
    Record,
    RecordComponent,
    TextSpan,
    View,
    canonical_table_name_for_slot,
    create_bbox,
    is_bbox,
)


def is_annotation_schema(cls: type) -> bool:
    """Check whether a schema class is an annotation schema."""
    return isinstance(cls, type) and (issubclass(cls, EntityAnnotation) or issubclass(cls, EntityGroupAnnotation))


@dataclass(frozen=True)
class AnnotationSource:
    """Default source metadata attached to imported annotations."""

    source_type: str
    source_name: str


class FolderRecordFactory:
    """Create record rows and default record metadata for folder imports."""

    def __init__(self, record_schema: type[Record]) -> None:
        """Initialize the factory with the record schema."""
        self.record_schema = record_schema

    def create_record(self, **record_metadata: Any) -> Record:
        """Instantiate one record row."""
        return self.record_schema(**record_metadata)

    def build_default_custom_metadata_record(self) -> dict[str, Any]:
        """Build default values for record custom fields when metadata is absent."""
        custom_record_metadata: dict[str, Any] = {}
        custom_fields = list(set(self.record_schema.field_names()) - set(Record.field_names()))
        for field in custom_fields:
            field_type = self.record_schema.__annotations__[field]
            custom_record_metadata[field] = field_type()
        return custom_record_metadata


class FolderMessageFactory:
    """Create message annotations from folder metadata payloads."""

    def __init__(self, source: AnnotationSource, normalize_view_name_alias) -> None:
        """Initialize the factory with source metadata and view-name normalizer."""
        self.source = source
        self.normalize_view_name_alias = normalize_view_name_alias

    def create_messages(
        self,
        record: Record,
        views_data: list[tuple[str, View]],
        raw_messages_data: list[Any],
    ) -> dict[str, list[RecordComponent]]:
        """Create message rows for conversations or flat message lists."""

        def resolve_view_target(target_name: str | None, fallback: tuple[str, View]) -> tuple[str, View]:
            target_name = self.normalize_view_name_alias(target_name)
            if target_name is None:
                return fallback
            for candidate_name, candidate_view in views_data:
                if candidate_name == target_name:
                    return candidate_name, candidate_view
            return fallback

        def message_entity_ids(payload: dict[str, Any]) -> list[str]:
            entity_ids = payload.get("entity_ids")
            if entity_ids is None:
                entity_ids = payload.get("referenced_entity_ids")
            if entity_ids is None and payload.get("entity_id"):
                entity_ids = [payload["entity_id"]]
            return list(entity_ids or [])

        def update_view_target(
            content: str, view_rows: list[tuple[str, View]], default_target: tuple[str, View]
        ) -> tuple[str, View]:
            match = re.match(r".*<image (\d)>.*", content)
            if match is None:
                return default_target
            for group in match.groups():
                num = int(group) - 1
                if 0 <= num < len(view_rows):
                    return view_rows[num]
            return default_target

        annotations: dict[str, list[RecordComponent]] = defaultdict(list)
        default_user = "import"
        conversations: list[list[Any]] = []

        if not isinstance(raw_messages_data, list):
            return annotations

        if raw_messages_data and all(isinstance(data, dict) and "type" in data for data in raw_messages_data):
            conversations = [raw_messages_data]
        elif all(isinstance(data, list) for data in raw_messages_data):
            conversations = raw_messages_data
        elif all(isinstance(data, dict) for data in raw_messages_data):
            conversations = [raw_messages_data]

        for conv in conversations:
            view_name, view = views_data[0]
            default_target = (view_name, view)
            conversation_id = shortuuid.uuid()
            message_number = 0

            for entry in conv:
                if "question" not in entry:
                    target_view_name, target_view = resolve_view_target(entry.get("view_name"), default_target)
                    message_type = entry.get("type", "QUESTION")
                    annotations[canonical_table_name_for_slot("message")].append(
                        Message(
                            id=entry.get("id", shortuuid.uuid()),
                            record_id=record.id,
                            entity_ids=message_entity_ids(entry),
                            source_type=entry.get("source_type", self.source.source_type),
                            source_name=entry.get("source_name", self.source.source_name),
                            view_id=target_view.id,
                            conversation_id=entry.get("conversation_id", conversation_id),
                            number=entry.get("number", message_number),
                            user=entry.get("user", default_user),
                            type=message_type,
                            content=entry.get("content", ""),
                            choices=entry.get("choices", []),
                            question_type=entry.get("question_type", "OPEN") if message_type == "QUESTION" else None,
                        )
                    )
                    message_number = max(message_number + 1, entry.get("number", message_number) + 1)
                    continue

                question = dict(entry.get("question", {}))
                if "user" not in question:
                    question["user"] = default_user

                content = question.get("content")
                if not content:
                    raise ValueError(f"No text content found for question in record {record}")

                _target_view_name, target_view = update_view_target(content, views_data, default_target)
                annotations[canonical_table_name_for_slot("message")].append(
                    Message(
                        id=shortuuid.uuid(),
                        record_id=record.id,
                        source_type=self.source.source_type,
                        source_name=self.source.source_name,
                        view_id=target_view.id,
                        conversation_id=conversation_id,
                        number=message_number,
                        type="QUESTION",
                        user=question["user"],
                        content=content,
                        choices=question.get("choices", []),
                        question_type=question.get("question_type", "OPEN"),
                        entity_ids=message_entity_ids(question),
                    )
                )
                message_number += 1

                response = entry.get("response", None)
                responses = [response] if isinstance(response, dict) else entry.get("responses", [])
                if not isinstance(responses, list):
                    responses = [responses]

                for response in responses:
                    if "user" not in response:
                        response["user"] = default_user
                    annotations[canonical_table_name_for_slot("message")].append(
                        Message(
                            id=shortuuid.uuid(),
                            record_id=record.id,
                            source_type=self.source.source_type,
                            source_name=self.source.source_name,
                            view_id=target_view.id,
                            conversation_id=conversation_id,
                            number=message_number,
                            type="ANSWER",
                            user=response["user"],
                            content=response.get("content", ""),
                            choices=[],
                            entity_ids=message_entity_ids(response) or message_entity_ids(question),
                        )
                    )
                    message_number += 1

        return annotations


class FolderEntityFactory:
    """Create entity rows and attached annotations from folder metadata."""

    def __init__(
        self,
        *,
        schemas: dict[str, type],
        source: AnnotationSource,
        normalize_view_name_alias,
    ) -> None:
        """Initialize the factory with schemas, source metadata, and view-name normalizer."""
        self.schemas = schemas
        self.source = source
        self.normalize_view_name_alias = normalize_view_name_alias
        self.annotation_alias_map = {
            "bbox": canonical_table_name_for_slot("bbox"),
            "mask": canonical_table_name_for_slot("mask"),
            "keypoint": canonical_table_name_for_slot("keypoint"),
            "text_span": canonical_table_name_for_slot("text_span"),
        }

    def create_objects_entities(
        self,
        record: Record,
        views_data: list[tuple[str, View]],
        entity_name: str,
        entity_schema: type[Entity],
        entities_data: list[dict[str, Any]],
    ) -> tuple[dict[str, list[Entity]], dict[str, list[RecordComponent]]]:
        """Create entity rows and attached annotations for one entity payload."""
        entities: dict[str, list[Entity]] = defaultdict(list)
        annotations: dict[str, list[RecordComponent]] = defaultdict(list)

        if not isinstance(entities_data, list):
            raise ValueError("Entity payload must be a list of entity objects.")

        views_by_name = dict(views_data)

        for entry in entities_data:
            if not isinstance(entry, dict):
                raise ValueError("Each entity entry must be a dictionary.")

            entity_id = shortuuid.uuid()
            entity_payload = {key: value for key, value in entry.items() if key != "annotations"}
            unknown_attrs = set(entity_payload) - set(entity_schema.model_fields.keys())
            if unknown_attrs:
                unknown = ", ".join(sorted(unknown_attrs))
                raise ValueError(f"Unknown entity attributes for {entity_name}: {unknown}.")

            entities[entity_name].append(entity_schema(id=entity_id, record_id=record.id, **entity_payload))

            annotations_payload = entry.get("annotations", {})
            if annotations_payload is None:
                continue
            if not isinstance(annotations_payload, dict):
                raise ValueError("Entity annotations must be grouped by view name.")

            for raw_view_name, annotation_group in annotations_payload.items():
                view_name = self.normalize_view_name_alias(raw_view_name)
                if view_name not in views_by_name:
                    raise ValueError(f"view_name '{view_name}' not found in views: {[n for n, _ in views_data]}")
                if annotation_group is None:
                    continue
                if not isinstance(annotation_group, dict):
                    raise ValueError(f"Annotations for view '{view_name}' must be a dictionary.")
                view = views_by_name[view_name]
                frame_index = view.frame_index if hasattr(view, "frame_index") else -1

                for attr, annotation_value in annotation_group.items():
                    attr = self.annotation_alias_map.get(attr, attr)
                    if annotation_value is None:
                        continue
                    if attr not in self.schemas:
                        raise ValueError(f"Attribute {attr} not found in schemas.")
                    schema = self.schemas[attr]
                    if not is_annotation_schema(schema):
                        raise ValueError(
                            f"Attribute {attr} must be an annotation schema"
                            " (EntityAnnotation or EntityGroupAnnotation subclass)"
                        )
                    annotations.setdefault(attr, [])
                    annotations[attr].append(
                        self._create_entity_annotation(
                            schema=schema,
                            annotation_value=annotation_value,
                            record=record,
                            view=view,
                            frame_index=frame_index,
                            entity_id=entity_id,
                        )
                    )
        return entities, annotations

    def _create_entity_annotation(
        self,
        *,
        schema: type,
        annotation_value: Any,
        record: Record,
        view: View,
        frame_index: int,
        entity_id: str,
    ) -> RecordComponent:
        if isinstance(annotation_value, Mapping):
            return create_instance_of_schema(
                schema,
                id=shortuuid.uuid(),
                record_id=record.id,
                view_id=view.id,
                frame_id=view.id,
                frame_index=frame_index,
                entity_id=entity_id,
                source_type=self.source.source_type,
                source_name=self.source.source_name,
                **annotation_value,
            )

        if is_bbox(schema, True):
            return create_bbox(
                id=shortuuid.uuid(),
                record_id=record.id,
                view_id=view.id,
                frame_id=view.id,
                frame_index=frame_index,
                entity_id=entity_id,
                source_type=self.source.source_type,
                source_name=self.source.source_name,
                coords=annotation_value,
                format="xywh",
                is_normalized=all(0 <= x <= 1 for x in annotation_value),
                confidence=1.0,
            )

        if schema is TextSpan and isinstance(annotation_value, str):
            return create_instance_of_schema(
                schema,
                id=shortuuid.uuid(),
                record_id=record.id,
                view_id=view.id,
                entity_id=entity_id,
                source_type=self.source.source_type,
                source_name=self.source.source_name,
                mention=annotation_value,
                spans_start=[],
                spans_end=[],
            )

        raise ValueError(f"Schema {schema} not supported for entity annotation creation.")
