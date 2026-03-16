# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pixano.schemas import canonical_table_name_for_slot


@dataclass
class MetadataIssueAggregate:
    """Aggregates repeated metadata issues with sample locations."""

    count: int = 0
    samples: list[str] = field(default_factory=list)

    def add(self, location: str) -> None:
        """Record one occurrence of an issue at the given location."""
        self.count += 1
        if len(self.samples) < 3 and location not in self.samples:
            self.samples.append(location)


@dataclass
class MetadataValidationReport:
    """Validation summary for folder metadata preflight."""

    split_count: int = 0
    row_count: int = 0
    warnings: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    errors: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    aliases: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    inferred: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    normalized_examples: list[str] = field(default_factory=list)

    @property
    def warning_count(self) -> int:
        """Return the total number of warnings, aliases, and inferred issues."""
        return (
            sum(issue.count for issue in self.warnings.values())
            + sum(issue.count for issue in self.aliases.values())
            + sum(issue.count for issue in self.inferred.values())
        )

    @property
    def error_count(self) -> int:
        """Return the total number of errors."""
        return sum(issue.count for issue in self.errors.values())

    @property
    def is_valid(self) -> bool:
        """Return True if no errors were recorded."""
        return self.error_count == 0

    def add_warning(self, code: str, location: str) -> None:
        """Add a warning issue for the given code and location."""
        self.warnings.setdefault(code, MetadataIssueAggregate()).add(location)

    def add_error(self, code: str, location: str) -> None:
        """Add an error issue for the given code and location."""
        self.errors.setdefault(code, MetadataIssueAggregate()).add(location)

    def add_alias(self, source_key: str, target_key: str, location: str) -> None:
        """Record a key alias mapping from source_key to target_key."""
        self.aliases.setdefault(f"{source_key} -> {target_key}", MetadataIssueAggregate()).add(location)

    def add_inferred(self, description: str, location: str) -> None:
        """Record an inferred value for the given description and location."""
        self.inferred.setdefault(description, MetadataIssueAggregate()).add(location)

    def add_normalized_example(self, description: str) -> None:
        """Record a sample normalized-key transformation for the report."""
        if description not in self.normalized_examples and len(self.normalized_examples) < 3:
            self.normalized_examples.append(description)


class FolderMetadataService:
    """Normalizes and validates ``metadata.jsonl`` rows for folder imports."""

    def __init__(
        self,
        *,
        source_dir: Path,
        metadata_filename: str,
        record_field_names: set[str],
        views_schema: dict[str, type],
        entities_schema: dict[str, type],
        entity_dynamic_states_schema: dict[str, type],
        annotations_schema: dict[str, type],
        resolve_view_files: Callable[[str, Any, type], list[Path]],
    ) -> None:
        """Initialize the metadata service with schema definitions and source directory."""
        self.source_dir = source_dir
        self.metadata_filename = metadata_filename
        self.record_field_names = record_field_names
        self.views_schema = views_schema
        self.entities_schema = entities_schema
        self.entity_dynamic_states_schema = entity_dynamic_states_schema
        self.annotations_schema = annotations_schema
        self._resolve_view_files = resolve_view_files

    @staticmethod
    def normalize_metadata_key(key: str) -> str:
        """Normalize a metadata key for case-insensitive matching."""
        return key.strip().lower()

    @staticmethod
    def is_media_path_token(value: str) -> bool:
        """Return ``True`` when the value looks like a media path or glob."""
        token = value.strip()
        if token == "":
            return False
        if any(c in token for c in ("*", "?", "[", "]")):
            return True
        if "/" in token or "\\" in token:
            return True
        suffix = Path(token).suffix
        return suffix != "" and suffix[1:].isalpha()

    def normalize_view_name_alias(self, view_name: str | None) -> str | None:
        """Resolve a metadata view alias to its declared logical name."""
        if view_name is None:
            return None
        return self.metadata_alias_map().get(self.normalize_metadata_key(view_name), view_name)

    def metadata_alias_map(self) -> dict[str, str]:
        """Build accepted metadata aliases from the declared schema."""
        from pixano.schemas import PDF, Image, SequenceFrame, Text

        alias_map: dict[str, str] = {}
        for view_name, view_schema in self.views_schema.items():
            normalized_view_name = self.normalize_metadata_key(view_name)
            alias_map[normalized_view_name] = view_name
            if issubclass(view_schema, (Image, SequenceFrame)):
                alias_map[f"{normalized_view_name}_image"] = view_name
            elif issubclass(view_schema, Text):
                alias_map[f"{normalized_view_name}_text"] = view_name
            elif issubclass(view_schema, PDF):
                alias_map[f"{normalized_view_name}_pdf"] = view_name
        if len(self.entities_schema) == 1:
            entity_name = next(iter(self.entities_schema))
            alias_map["objects"] = entity_name
            alias_map["object"] = entity_name
        if canonical_table_name_for_slot("message") in self.annotations_schema:
            alias_map["conversations"] = canonical_table_name_for_slot("message")
            alias_map["conversation"] = canonical_table_name_for_slot("message")
        for singular, slot_name in (
            ("bbox", "bbox"),
            ("mask", "mask"),
            ("keypoint", "keypoint"),
            ("text_span", "text_span"),
        ):
            table_name = canonical_table_name_for_slot(slot_name)
            if table_name in self.annotations_schema:
                alias_map[singular] = table_name
        return alias_map

    def resolve_schema_key_from_value(self, value: Any) -> str | None:
        """Resolve an unknown metadata key from payload shape when unambiguous."""
        candidates: list[str] = []

        if self._matches_single_view_payload(value):
            candidates.append(next(iter(self.views_schema.keys())))

        entity_candidates = list(self.entities_schema.keys())
        if len(entity_candidates) == 1 and self._matches_entity_payload(entity_candidates[0], value):
            candidates.append(entity_candidates[0])

        if len(self.entity_dynamic_states_schema) == 1:
            state_name = next(iter(self.entity_dynamic_states_schema.keys()))
            if self._matches_entity_dynamic_state_payload(state_name, value):
                candidates.append(state_name)

        unique_candidates = list(dict.fromkeys(candidates))
        if len(unique_candidates) == 1:
            return unique_candidates[0]
        return None

    def normalize_dataset_piece(self, dataset_piece: dict[str, Any]) -> dict[str, Any]:
        """Normalize one metadata row without collecting a report."""
        return self.normalize_dataset_piece_with_report(dataset_piece, None, "", 0, "default")

    def normalize_dataset_piece_with_report(
        self,
        dataset_piece: dict[str, Any],
        report: MetadataValidationReport | None,
        split_name: str,
        line_number: int,
        validation_mode: str,
    ) -> dict[str, Any]:
        """Normalize one metadata row and record normalization events."""
        strict = validation_mode == "strict"
        location = f"{split_name}:{line_number}" if split_name else str(line_number)
        normalized_piece = self._normalize_canonical_structure(dict(dataset_piece), report, location, strict)
        known_schema_keys = self._known_top_level_keys()
        alias_map = self.metadata_alias_map()
        normalized_to_keys: dict[str, list[str]] = defaultdict(list)
        for schema_key in known_schema_keys:
            normalized_to_keys[self.normalize_metadata_key(schema_key)].append(schema_key)

        for source_key in list(normalized_piece.keys()):
            if source_key in known_schema_keys:
                continue

            source_value = normalized_piece[source_key]
            normalized_source_key = self.normalize_metadata_key(source_key)
            case_insensitive_matches = normalized_to_keys.get(normalized_source_key, [])

            target_key = case_insensitive_matches[0] if len(case_insensitive_matches) == 1 else None
            is_alias = False
            if target_key is None:
                target_key = alias_map.get(normalized_source_key)
                is_alias = target_key is not None
            if target_key is None:
                inferred_key = self.resolve_schema_key_from_value(source_value)
                if inferred_key is not None:
                    if strict:
                        if report is not None:
                            report.add_error("inferred_metadata_key", location)
                    else:
                        target_key = inferred_key
                        if report is not None:
                            report.add_inferred(f"{source_key} -> {target_key}", location)
                            report.add_normalized_example(f"{source_key} -> {target_key}")
            if target_key is None:
                continue

            if strict and (is_alias or target_key != source_key):
                if report is not None:
                    report.add_error("aliased_metadata_key", location)
                continue

            if report is not None and is_alias:
                report.add_alias(source_key, target_key, location)
                report.add_normalized_example(f"{source_key} -> {target_key}")
            elif report is not None and target_key != source_key:
                report.add_warning("normalized_metadata_key", location)
                report.add_normalized_example(f"{source_key} -> {target_key}")

            source_value = normalized_piece.pop(source_key)
            if target_key not in normalized_piece:
                normalized_piece[target_key] = source_value

        return normalized_piece

    def validate_dataset_piece(
        self,
        dataset_piece: dict[str, Any],
        split_name: str,
        line_number: int,
        report: MetadataValidationReport,
        validation_mode: str,
    ) -> None:
        """Validate one metadata row against the declared schema."""
        location = f"{split_name}:{line_number}"
        normalized_piece = self.normalize_dataset_piece_with_report(
            dict(dataset_piece), report, split_name, line_number, validation_mode
        )
        known_top_level_keys = self._known_top_level_keys()
        for key, value in normalized_piece.items():
            if key in self.views_schema:
                if isinstance(value, list) and len(value) == 0:
                    continue
                files = self._resolve_view_files(split_name, value, self.views_schema[key])
                if not files:
                    report.add_error("missing_view_media", location)
                else:
                    report.add_normalized_example(f"{key} -> logical view '{key}'")
                continue
            if key in self.entities_schema:
                self._validate_entities_payload(value, self.entities_schema[key], split_name, line_number, report)
                continue
            if key in self.entity_dynamic_states_schema and isinstance(value, dict):
                self._validate_entity_payload(
                    value, self.entity_dynamic_states_schema[key], split_name, line_number, report, validation_mode
                )
                continue
            if key == canonical_table_name_for_slot("message") and not isinstance(value, list):
                report.add_error("invalid_messages_payload", location)
                continue
            if key not in known_top_level_keys:
                if validation_mode == "strict":
                    report.add_error("unknown_metadata_key", location)
                else:
                    report.add_warning("unknown_metadata_key", location)

    def preflight_metadata(self, validation_mode: str) -> MetadataValidationReport:
        """Validate every metadata row found in the source directory."""
        report = MetadataValidationReport()
        for split in self.source_dir.glob("*"):
            if not split.is_dir() or split.name.startswith("."):
                continue
            report.split_count += 1
            metadata_file = split / self.metadata_filename
            if not metadata_file.exists():
                continue
            with metadata_file.open("r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    stripped_line = raw_line.strip()
                    if not stripped_line:
                        continue
                    report.row_count += 1
                    try:
                        dataset_piece = json.loads(stripped_line)
                    except json.JSONDecodeError:
                        report.add_error("invalid_jsonl", f"{split.name}:{line_number}")
                        continue
                    if not isinstance(dataset_piece, dict):
                        report.add_error("invalid_metadata_row", f"{split.name}:{line_number}")
                        continue
                    self.validate_dataset_piece(dataset_piece, split.name, line_number, report, validation_mode)
        return report

    def _known_top_level_keys(self) -> set[str]:
        return (
            set(self.record_field_names)
            | set(self.views_schema.keys())
            | set(self.entities_schema.keys())
            | set(self.entity_dynamic_states_schema.keys())
            | set(self.annotations_schema.keys())
            | {"views", "annotation_files"}
            | {"fps"}
        )

    def _matches_single_view_payload(self, value: Any) -> bool:
        if len(self.views_schema) != 1:
            return False

        if isinstance(value, str):
            return self.is_media_path_token(value)
        if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
            return all(self.is_media_path_token(v) for v in value)
        return False

    def _matches_entity_payload(self, entity_name: str, value: Any) -> bool:
        if not isinstance(value, list):
            return False

        entity_schema = self.entities_schema[entity_name]
        return any(self._is_entity_entry_payload(entry, entity_schema) for entry in value)

    def _matches_entity_dynamic_state_payload(self, state_name: str, value: Any) -> bool:
        if not isinstance(value, dict):
            return False

        state_schema = self.entity_dynamic_states_schema[state_name]
        allowed_keys = set(state_schema.model_fields.keys()) | {"view_name"}  # type: ignore[attr-defined]
        return any(key in allowed_keys for key in value.keys())

    def _validate_entity_payload(
        self,
        payload: dict[str, Any],
        schema: type,
        split_name: str,
        line_number: int,
        report: MetadataValidationReport,
        validation_mode: str,
    ) -> None:
        location = f"{split_name}:{line_number}"
        normalized_view_name = (
            self.normalize_view_name_alias(payload.get("view_name")) if "view_name" in payload else None
        )
        if "view_name" in payload and normalized_view_name not in self.views_schema:
            report.add_error("invalid_view_name", location)
        lengths = {
            len(value)
            for key, value in payload.items()
            if key != "view_name" and not isinstance(value, dict) and isinstance(value, list)
        }
        if len(lengths) > 1:
            report.add_error("inconsistent_entity_lengths", location)
        allowed_keys = set(schema.model_fields) | set(self.annotations_schema) | {"view_name"}  # type: ignore[attr-defined]
        for key, value in payload.items():
            if key in {"view_name"}:
                continue
            if key in self.annotations_schema and isinstance(value, dict):
                nested_lengths = {len(v) for v in value.values() if isinstance(v, list)}
                if len(nested_lengths) > 1:
                    report.add_error("inconsistent_annotation_lengths", location)
                continue
            if key not in allowed_keys:
                if validation_mode == "strict":
                    report.add_error("unknown_entity_key", location)
                else:
                    report.add_warning("unknown_entity_key", location)

    def _validate_entities_payload(
        self,
        payload: Any,
        schema: type,
        split_name: str,
        line_number: int,
        report: MetadataValidationReport,
    ) -> None:
        location = f"{split_name}:{line_number}"
        if not isinstance(payload, list):
            report.add_error("invalid_entities_payload", location)
            return

        for entity_index, entity_payload in enumerate(payload, start=1):
            if not isinstance(entity_payload, dict):
                report.add_error("invalid_entity_entry", f"{location}#{entity_index}")
                continue
            self._validate_entity_entry(entity_payload, schema, f"{location}#{entity_index}", report)

    def _validate_entity_entry(
        self,
        payload: dict[str, Any],
        schema: type,
        location: str,
        report: MetadataValidationReport,
    ) -> None:
        annotations_payload = payload.get("annotations")
        allowed_keys = set(schema.model_fields) | {"annotations"}  # type: ignore[attr-defined]
        for key in payload:
            if key not in allowed_keys:
                report.add_warning("unknown_entity_key", location)

        if annotations_payload is None:
            return
        if not isinstance(annotations_payload, dict):
            report.add_error("invalid_entity_annotations", location)
            return

        for raw_view_name, annotation_group in annotations_payload.items():
            view_name = self.normalize_view_name_alias(raw_view_name)
            if view_name not in self.views_schema:
                report.add_error("invalid_view_name", location)
                continue
            if annotation_group is None:
                continue
            if not isinstance(annotation_group, dict):
                report.add_error("invalid_entity_annotations", location)
                continue
            for raw_annotation_name in annotation_group:
                annotation_name = self._canonical_annotation_name(raw_annotation_name)
                if annotation_name not in self.annotations_schema:
                    report.add_warning("unknown_entity_annotation", location)

    def _is_entity_entry_payload(self, payload: Any, schema: type) -> bool:
        if not isinstance(payload, dict):
            return False
        allowed_keys = set(schema.model_fields.keys()) | {"annotations"}  # type: ignore[attr-defined]
        return any(key in allowed_keys for key in payload)

    def _canonical_annotation_name(self, name: str) -> str:
        return self.metadata_alias_map().get(self.normalize_metadata_key(name), name)

    def _is_preferred_annotation_key(self, name: str) -> bool:
        return self.normalize_metadata_key(name) in {"bbox", "mask", "keypoint", "text_span", "message"}

    def _normalize_canonical_structure(
        self,
        dataset_piece: dict[str, Any],
        report: MetadataValidationReport | None,
        location: str,
        strict: bool,
    ) -> dict[str, Any]:
        normalized_piece = dict(dataset_piece)
        views_payload = normalized_piece.pop("views", None)
        if views_payload is not None:
            normalized_piece.update(self._normalize_views_payload(views_payload, report, location, strict))

        annotation_files_payload = normalized_piece.pop("annotation_files", None)
        if annotation_files_payload is not None:
            normalized_piece.update(
                self._normalize_annotation_files_payload(annotation_files_payload, report, location, strict)
            )

        entity_key = next(iter(self.entities_schema.keys()), None)
        if entity_key is not None and "entities" in normalized_piece and entity_key not in normalized_piece:
            entities_value = normalized_piece.pop("entities")
            normalized_piece[entity_key] = self._normalize_entities_list(entities_value, report, location, strict)

        return normalized_piece

    def _normalize_views_payload(
        self,
        payload: Any,
        report: MetadataValidationReport | None,
        location: str,
        strict: bool,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        normalized_views: dict[str, Any] = {}
        fps_values: set[float] = set()
        for raw_view_name, raw_value in payload.items():
            view_name = self.normalize_view_name_alias(raw_view_name)
            if view_name is None:
                continue
            resolved_view_name = view_name
            if strict and resolved_view_name != raw_view_name and report is not None:
                report.add_error("aliased_metadata_key", location)
                continue
            if report is not None and resolved_view_name != raw_view_name:
                report.add_alias(raw_view_name, resolved_view_name, location)
                report.add_normalized_example(f"{raw_view_name} -> logical view '{resolved_view_name}'")
            if isinstance(raw_value, dict):
                path_value = raw_value.get("path")
                if path_value is not None:
                    normalized_views[resolved_view_name] = path_value
                if "fps" in raw_value and raw_value["fps"] is not None:
                    fps_values.add(float(raw_value["fps"]))
            else:
                normalized_views[resolved_view_name] = raw_value
        if len(fps_values) == 1:
            normalized_views["fps"] = fps_values.pop()
        return normalized_views

    def _normalize_annotation_files_payload(
        self,
        payload: Any,
        report: MetadataValidationReport | None,
        location: str,
        strict: bool,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        normalized_annotations: dict[str, Any] = {}
        for raw_name, raw_value in payload.items():
            annotation_name = self._canonical_annotation_name(raw_name)
            is_preferred_key = self._is_preferred_annotation_key(raw_name)
            if strict and annotation_name != raw_name and not is_preferred_key and report is not None:
                report.add_error("aliased_metadata_key", location)
                continue
            if report is not None and annotation_name != raw_name and not is_preferred_key:
                report.add_alias(raw_name, annotation_name, location)
                report.add_normalized_example(f"{raw_name} -> {annotation_name}")
            if isinstance(raw_value, dict) and "path" in raw_value:
                normalized_annotations[annotation_name] = raw_value["path"]
            else:
                normalized_annotations[annotation_name] = raw_value
        return normalized_annotations

    def _normalize_entities_list(
        self,
        payload: Any,
        report: MetadataValidationReport | None,
        location: str,
        strict: bool,
    ) -> Any:
        if not isinstance(payload, list):
            return payload
        return [
            self._normalize_entity_entry(entry, report, location, strict)
            for entry in payload
            if isinstance(entry, dict)
        ]

    def _normalize_entity_entry(
        self,
        payload: dict[str, Any],
        report: MetadataValidationReport | None,
        location: str,
        strict: bool,
    ) -> dict[str, Any]:
        normalized_entry = dict(payload)
        annotations_payload = normalized_entry.get("annotations")
        if not isinstance(annotations_payload, dict):
            return normalized_entry

        normalized_annotations: dict[str, dict[str, Any]] = {}
        for raw_view_name, annotation_group in annotations_payload.items():
            view_name = self.normalize_view_name_alias(raw_view_name)
            if view_name is None:
                continue
            resolved_view_name = view_name
            if strict and resolved_view_name != raw_view_name and report is not None:
                report.add_error("aliased_metadata_key", location)
                continue
            if report is not None and resolved_view_name != raw_view_name:
                report.add_alias(raw_view_name, resolved_view_name, location)
            if not isinstance(annotation_group, dict):
                continue
            normalized_group: dict[str, Any] = {}
            for raw_annotation_name, annotation_value in annotation_group.items():
                annotation_name = self._canonical_annotation_name(raw_annotation_name)
                is_preferred_key = self._is_preferred_annotation_key(raw_annotation_name)
                if strict and annotation_name != raw_annotation_name and not is_preferred_key and report is not None:
                    report.add_error("aliased_metadata_key", location)
                    continue
                if report is not None and annotation_name != raw_annotation_name and not is_preferred_key:
                    report.add_alias(raw_annotation_name, annotation_name, location)
                normalized_group[annotation_name] = annotation_value
            normalized_annotations[resolved_view_name] = normalized_group
        normalized_entry["annotations"] = normalized_annotations
        return normalized_entry
