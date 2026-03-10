# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping

import numpy as np
import PIL.Image
import pyarrow.json as pa_json
import shortuuid
from lancedb.pydantic import LanceModel

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.utils import mosaic
from pixano.datasets.workspaces import WorkspaceType
from pixano.features.utils.creators import create_instance_of_schema
from pixano.schemas import (
    BBox,
    CompressedRLE,
    Entity,
    EntityAnnotation,
    EntityDynamicState,
    EntityGroupAnnotation,
    Image,
    KeyPoints,
    Message,
    PDF,
    Record,
    RecordComponent,
    SchemaGroup,
    SequenceFrame,
    Text,
    TextSpan,
    Tracklet,
    View,
    canonical_table_name_for_schema,
    canonical_table_name_for_slot,
    create_bbox,
    is_bbox,
    is_entity,
    is_entity_annotation,
    is_entity_dynamic_state,
    is_entity_group_annotation,
    is_sequence_frame,
    is_video,
    is_view,
)
from pixano.schemas.annotations.entity_annotation import AnnotationSourceKind
from pixano.schemas.annotations.compressed_rle import CompressedRLE, is_compressed_rle


# Union type for annotation base classes
_AnnotationBase = EntityAnnotation | EntityGroupAnnotation


@dataclass
class MetadataIssueAggregate:
    count: int = 0
    samples: list[str] = field(default_factory=list)

    def add(self, location: str) -> None:
        self.count += 1
        if len(self.samples) < 3 and location not in self.samples:
            self.samples.append(location)


@dataclass
class MetadataValidationReport:
    split_count: int = 0
    row_count: int = 0
    warnings: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    errors: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    aliases: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    inferred: dict[str, MetadataIssueAggregate] = field(default_factory=dict)
    normalized_examples: list[str] = field(default_factory=list)

    @property
    def warning_count(self) -> int:
        return (
            sum(issue.count for issue in self.warnings.values())
            + sum(issue.count for issue in self.aliases.values())
            + sum(issue.count for issue in self.inferred.values())
        )

    @property
    def error_count(self) -> int:
        return sum(issue.count for issue in self.errors.values())

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0

    def add_warning(self, code: str, location: str) -> None:
        self.warnings.setdefault(code, MetadataIssueAggregate()).add(location)

    def add_error(self, code: str, location: str) -> None:
        self.errors.setdefault(code, MetadataIssueAggregate()).add(location)

    def add_alias(self, source_key: str, target_key: str, location: str) -> None:
        self.aliases.setdefault(f"{source_key} -> {target_key}", MetadataIssueAggregate()).add(location)

    def add_inferred(self, description: str, location: str) -> None:
        self.inferred.setdefault(description, MetadataIssueAggregate()).add(location)

    def add_normalized_example(self, description: str) -> None:
        if description not in self.normalized_examples and len(self.normalized_examples) < 3:
            self.normalized_examples.append(description)


def _is_annotation(cls: type) -> bool:
    """Check if cls is an annotation schema (EntityAnnotation or EntityGroupAnnotation subclass)."""
    return isinstance(cls, type) and (issubclass(cls, EntityAnnotation) or issubclass(cls, EntityGroupAnnotation))


from ..dataset_builder import DatasetBuilder


class FolderBaseBuilder(DatasetBuilder):
    """This is a class for building datasets based on a folder structure.

    The folder structure should be as follows:
        - source_dir/{split}/{item}.{ext}
        - source_dir/{split}/metadata.jsonl

    The metadata file should be a jsonl file with the following format:
    ```json
        [
            {
                "item": "item1",
                "metadata1": "value1",
                "metadata2": "value2",
                ...
                "entities": {
                    "attr1": [val1, val2, ...],
                    "attr2": [val1, val2, ...],
                    ...
                }
            },
            ...
        ]
    ```

    Note:
        Multiple views are supported. When entity data in ``metadata.jsonl`` includes a ``"view_name"`` key
        whose value matches a view field name, that entity (and its annotations) will reference the specified
        view. Without ``"view_name"``, the first view is used by default.
        If you give a list of images for a single view field, they will be put in a mosaic.

    Attributes:
        source_dir: The source directory for the dataset.
        METADATA_FILENAME: The metadata filename.
        EXTENSIONS: The list of supported extensions.
        WORKSPACE_TYPE: The workspace type of the dataset.
    """

    METADATA_FILENAME: str = "metadata.jsonl"
    EXTENSIONS: list[str]
    WORKSPACE_TYPE = WorkspaceType.UNDEFINED
    DEFAULT_INFO: DatasetInfo | None = None

    def __init__(
        self,
        source_dir: Path | str,
        library_dir: Path | str,
        info: DatasetInfo,
        metadata_validation_mode: str = "default",
        use_image_name_as_id: bool = False,
        target_name: str | None = None,
    ) -> None:
        """Initialize the `FolderBaseBuilder`.

        Args:
            source_dir: The source directory containing the raw media files
                to import.  All media is embedded in the database as blobs.
            library_dir: The global directory for Pixano datasets library.
            info: User informations (name, description, ...) for the dataset.
            metadata_validation_mode: Metadata validation mode ("default" or "strict").
            use_image_name_as_id: If True, use image base name as image id.
                                  Images MUST have unique base names.
                                  When no metadata file exists, also use it as record id,
                                  else, use 'record_#'
                                  This allows to reuse image embeddings after dataset overwrite.
            target_name: If provided, use this name for the target directory in the library
                instead of deriving it from source_dir name.
        """
        info = self._merge_with_default_info(info)
        if not info.tables:
            raise ValueError("DatasetInfo must define at least one record schema and one view.")
        if info.workspace != self.WORKSPACE_TYPE:
            raise ValueError(
                f"DatasetInfo.workspace={info.workspace.value} is incompatible with {self.__class__.__name__}."
            )
        if metadata_validation_mode not in {"default", "strict"}:
            raise ValueError(
                f"metadata_validation_mode should be 'default' or 'strict' but got {metadata_validation_mode}"
            )

        self.use_image_name_as_id = use_image_name_as_id
        self.metadata_validation_mode = metadata_validation_mode
        self._metadata_report_cache: dict[str, MetadataValidationReport] = {}
        info.storage_mode = "embedded"

        self.source_dir = Path(source_dir)
        if not self.source_dir.is_dir():
            raise ValueError(f"Source directory does not exist: {self.source_dir}")

        if target_name is not None:
            target_dir = Path(library_dir) / target_name
        else:
            target_dir = Path(library_dir) / self.source_dir.name
        super().__init__(target_dir=target_dir, info=info)

        self.views_schema: dict[str, type[View]] = dict(self.info.views)
        self.entities_schema: dict[str, type[Entity]] = {}
        self.entity_dynamic_states_schema: dict[str, type[EntityDynamicState]] = {}
        self.annotations_schema: dict[str, type[RecordComponent]] = {}

        if self.info.entity is not None:
            self.entities_schema[canonical_table_name_for_slot("entity")] = self.info.entity
        if self.info.entity_dynamic_state is not None:
            self.entity_dynamic_states_schema[canonical_table_name_for_slot("entity_dynamic_state")] = (
                self.info.entity_dynamic_state
            )
        if self.info.bbox is not None:
            self.annotations_schema[canonical_table_name_for_slot("bbox")] = self.info.bbox
        if self.info.mask is not None:
            self.annotations_schema[canonical_table_name_for_slot("mask")] = self.info.mask
        if self.info.keypoint is not None:
            self.annotations_schema[canonical_table_name_for_slot("keypoint")] = self.info.keypoint
        if self.info.tracklet is not None:
            self.annotations_schema[canonical_table_name_for_slot("tracklet")] = self.info.tracklet
        if self.info.message is not None:
            self.annotations_schema[canonical_table_name_for_slot("message")] = self.info.message
        if self.info.text_span is not None:
            self.annotations_schema[canonical_table_name_for_slot("text_span")] = self.info.text_span

        if not self.views_schema or not self.entities_schema:
            raise ValueError("At least one view and one entity schema must be defined in DatasetInfo.")

    def _merge_with_default_info(self, info: DatasetInfo) -> DatasetInfo:
        default_info = self.DEFAULT_INFO
        if default_info is None:
            return info

        merged_data = info.model_dump(exclude={"tables"})
        default_data = default_info.model_dump(exclude={"tables"})
        for key, value in default_data.items():
            if key == "views":
                if not merged_data.get("views"):
                    merged_data["views"] = value
                continue
            current_value = merged_data.get(key)
            if current_value in (None, "") or (
                key == "workspace" and current_value in (WorkspaceType.UNDEFINED, WorkspaceType.UNDEFINED.value)
            ):
                merged_data[key] = value
        return DatasetInfo.model_validate(merged_data)

    @staticmethod
    def _normalize_metadata_key(key: str) -> str:
        return key.strip().lower()

    @staticmethod
    def _is_media_path_token(value: str) -> bool:
        token = value.strip()
        if token == "":
            return False
        if any(c in token for c in ("*", "?", "[", "]")):
            return True
        if "/" in token or "\\" in token:
            return True
        suffix = Path(token).suffix
        return suffix != "" and suffix[1:].isalpha()

    def _matches_single_view_payload(self, value: Any) -> bool:
        """Check if a metadata value can be routed to the single declared view field."""
        if len(self.views_schema) != 1:
            return False

        if isinstance(value, str):
            return self._is_media_path_token(value)
        if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
            return all(self._is_media_path_token(v) for v in value)
        return False

    def _matches_entity_payload(self, entity_name: str, value: Any) -> bool:
        """Check if a metadata value matches a declared entity field."""
        if not isinstance(value, dict):
            return False

        entity_schema = self.entities_schema[entity_name]
        allowed_keys = set(entity_schema.model_fields.keys()) | set(self.annotations_schema.keys()) | {"view_name"}
        return any(key in allowed_keys for key in value.keys())

    def _matches_entity_dynamic_state_payload(self, state_name: str, value: Any) -> bool:
        """Check if a metadata value matches a declared entity dynamic state field."""
        if not isinstance(value, dict):
            return False

        state_schema = self.entity_dynamic_states_schema[state_name]
        allowed_keys = set(state_schema.model_fields.keys()) | {"view_name"}
        return any(key in allowed_keys for key in value.keys())

    def _resolve_schema_key_from_value(self, value: Any) -> str | None:
        """Resolve an unknown metadata key from payload shape using declared schema only."""
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

    def _normalize_dataset_piece_keys(self, dataset_piece: dict[str, Any]) -> dict[str, Any]:
        """Normalize metadata keys to schema field names when mapping is unambiguous."""
        return self._normalize_dataset_piece_keys_with_report(dataset_piece, None, "", 0, "default")

    def _normalize_dataset_piece_keys_with_report(
        self,
        dataset_piece: dict[str, Any],
        report: MetadataValidationReport | None,
        split_name: str,
        line_number: int,
        validation_mode: str,
    ) -> dict[str, Any]:
        strict = validation_mode == "strict"
        location = f"{split_name}:{line_number}" if split_name else str(line_number)
        normalized_piece = dict(dataset_piece)
        known_schema_keys = (
            set(self.record_schema.model_fields.keys())
            | set(self.views_schema.keys())
            | set(self.entities_schema.keys())
            | set(self.entity_dynamic_states_schema.keys())
            | set(self.annotations_schema.keys())
            | {"fps"}
        )
        alias_map = self._metadata_alias_map()
        normalized_to_keys: dict[str, list[str]] = defaultdict(list)
        for schema_key in known_schema_keys:
            normalized_to_keys[self._normalize_metadata_key(schema_key)].append(schema_key)

        for source_key in list(normalized_piece.keys()):
            if source_key in known_schema_keys:
                continue

            source_value = normalized_piece[source_key]
            normalized_source_key = self._normalize_metadata_key(source_key)
            case_insensitive_matches = normalized_to_keys.get(normalized_source_key, [])

            target_key = case_insensitive_matches[0] if len(case_insensitive_matches) == 1 else None
            is_alias = False
            if target_key is None:
                target_key = alias_map.get(normalized_source_key)
                is_alias = target_key is not None
            if target_key is None:
                inferred_key = self._resolve_schema_key_from_value(source_value)
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

    def _metadata_alias_map(self) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for view_name, view_schema in self.views_schema.items():
            normalized_view_name = self._normalize_metadata_key(view_name)
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
        for singular, slot_name in (("bbox", "bbox"), ("mask", "mask"), ("keypoint", "keypoint")):
            table_name = canonical_table_name_for_slot(slot_name)
            if table_name in self.annotations_schema:
                alias_map[singular] = table_name
        return alias_map

    def _normalize_view_name_alias(self, view_name: str | None) -> str | None:
        if view_name is None:
            return None
        return self._metadata_alias_map().get(self._normalize_metadata_key(view_name), view_name)

    def _resolve_view_files(self, split_name: str, raw_value: Any, view_schema: type[View]) -> list[Path]:
        split_dir = self.source_dir / split_name
        if is_sequence_frame(view_schema):
            if isinstance(raw_value, str) and any(c in raw_value for c in ("*", "?", "[")):
                frame_files = sorted(split_dir.glob(raw_value))
                if not frame_files:
                    frame_files = sorted(self.source_dir.glob(raw_value))
                return frame_files
            if isinstance(raw_value, list):
                resolved_files: list[Path] = []
                for item in raw_value:
                    path = self.source_dir / Path(item)
                    if not path.is_file():
                        path = split_dir / Path(item)
                    if path.is_file():
                        resolved_files.append(path)
                return resolved_files

        if isinstance(raw_value, list):
            if len(raw_value) == 0:
                return []
            if len(raw_value) > 1:
                resolved_files: list[Path] = []
                for item in raw_value:
                    path = self.source_dir / Path(item)
                    if not path.is_file():
                        path = split_dir / Path(item)
                    if path.is_file():
                        resolved_files.append(path)
                return resolved_files
            raw_value = raw_value[0]

        if isinstance(raw_value, str):
            path = self.source_dir / (
                Path(raw_value) if split_name == Path(raw_value).parts[0] else Path(split_name) / Path(raw_value)
            )
            return [path] if path.is_file() else []
        return []

    def _validate_entity_payload(
        self,
        payload: dict[str, Any],
        schema: type[LanceModel],
        split_name: str,
        line_number: int,
        report: MetadataValidationReport,
        validation_mode: str,
    ) -> None:
        location = f"{split_name}:{line_number}"
        normalized_view_name = (
            self._normalize_view_name_alias(payload.get("view_name")) if "view_name" in payload else None
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
        allowed_keys = set(schema.model_fields) | set(self.annotations_schema) | {"view_name"}
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

    def _validate_dataset_piece(
        self,
        dataset_piece: dict[str, Any],
        split_name: str,
        line_number: int,
        report: MetadataValidationReport,
        validation_mode: str,
    ) -> None:
        location = f"{split_name}:{line_number}"
        normalized_piece = self._normalize_dataset_piece_keys_with_report(
            dict(dataset_piece), report, split_name, line_number, validation_mode
        )
        known_top_level_keys = (
            set(self.record_schema.model_fields)
            | set(self.views_schema)
            | set(self.entities_schema)
            | set(self.entity_dynamic_states_schema)
            | set(self.annotations_schema)
            | {"fps"}
        )
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
            if key in self.entities_schema and isinstance(value, dict):
                self._validate_entity_payload(
                    value, self.entities_schema[key], split_name, line_number, report, validation_mode
                )
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

    def preflight_metadata(self, validation_mode: str | None = None) -> MetadataValidationReport:
        mode = validation_mode or self.metadata_validation_mode
        cached_report = self._metadata_report_cache.get(mode)
        if cached_report is not None:
            return cached_report

        report = MetadataValidationReport()
        for split in self.source_dir.glob("*"):
            if not split.is_dir() or split.name.startswith("."):
                continue
            report.split_count += 1
            metadata_file = split / self.METADATA_FILENAME
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
                    self._validate_dataset_piece(dataset_piece, split.name, line_number, report, mode)

        self._metadata_report_cache[mode] = report
        return report

    def generate_data(
        self,
    ) -> Iterator[dict[str, LanceModel | list[LanceModel]]]:
        """Generate data from the source directory.

        Returns:
            An iterator over the data following the dataset schemas.
        """
        report = self.preflight_metadata(self.metadata_validation_mode)
        if not report.is_valid:
            raise ValueError(
                f"Metadata validation failed with {report.error_count} errors. "
                "Run the CLI with --dry-run to inspect the validation summary."
            )
        self._default_source_type = AnnotationSourceKind.OTHER.value
        self._default_source_name = "Builder"
        for split in self.source_dir.glob("*"):
            if not split.is_dir() or split.name.startswith("."):
                continue

            try:
                dataset_pieces = self._read_metadata(split / self.METADATA_FILENAME)
            except FileNotFoundError:
                dataset_pieces = None

            if dataset_pieces is None:
                for view_file in sorted(split.glob("**/*")):
                    # only consider {split}/**/{record}.{ext} files
                    if not view_file.is_file() or view_file.suffix not in self.EXTENSIONS:
                        continue
                    # create record with default values for custom fields
                    custom_record_metadata = self._build_default_custom_metadata_record()
                    custom_record_metadata["id"] = view_file.stem
                    custom_record_metadata["split"] = split.name
                    record = self._create_record(**custom_record_metadata)
                    # create view
                    view_name_nojsonl, view_schema_nojsonl = list(self.views_schema.items())[0]  # only one view
                    view = self._create_view(record, view_file, view_name_nojsonl, view_schema_nojsonl)
                    yield {
                        self.record_table_name: record,
                        canonical_table_name_for_schema(view_schema_nojsonl): view,
                    }
                continue

            for i, dataset_piece in enumerate(dataset_pieces):
                dataset_piece = self._normalize_dataset_piece_keys(dict(dataset_piece))
                # Extract fps before record_metadata collection (Record has no fps field)
                fps = dataset_piece.pop("fps", None)
                frame_period_ms = 1000.0 / (fps if fps is not None else 24.0)

                record_metadata = {}
                for k in dataset_piece.keys():
                    if (
                        k not in self.views_schema
                        and k not in self.entities_schema
                        and k not in self.entity_dynamic_states_schema
                        and k not in self.annotations_schema
                    ):
                        record_metadata.update({k: dataset_piece.get(k, None)})
                for k in record_metadata.keys():
                    dataset_piece.pop(k, None)

                # create record
                if "id" not in record_metadata:
                    record_metadata["id"] = (
                        f"record_{split.name}_{i}" if self.use_image_name_as_id else shortuuid.uuid()
                    )
                if "split" not in record_metadata:
                    record_metadata["split"] = split.name
                record = self._create_record(**record_metadata)

                # create view
                views_data: list[tuple[str, View]] = []
                frame_views_by_stem: dict[str, tuple[str, View, int, float]] = {}
                for k, v in dataset_piece.items():
                    if k in self.views_schema:
                        view_name = k
                        view_schema = self.views_schema.get(view_name)
                        if view_schema is not None:
                            # Handle SequenceFrame views: expand glob patterns into individual frames
                            if is_sequence_frame(view_schema):
                                if isinstance(v, str) and any(c in v for c in ("*", "?", "[")):
                                    frame_files = sorted((self.source_dir / split.name).glob(v))
                                    if not frame_files:
                                        frame_files = sorted(self.source_dir.glob(v))
                                elif isinstance(v, list):
                                    frame_files = []
                                    for f in v:
                                        fp = self.source_dir / Path(f)
                                        if not fp.is_file():
                                            fp = self.source_dir / split.name / Path(f)
                                        if fp.is_file():
                                            frame_files.append(fp)
                                else:
                                    fp = self.source_dir / (
                                        Path(v) if split.name == Path(v).parts[0] else Path(split.name) / Path(v)
                                    )
                                    frame_files = [fp] if fp.is_file() else []

                                for idx, frame_file in enumerate(frame_files):
                                    if frame_file.suffix not in self.EXTENSIONS:
                                        continue
                                    timestamp = idx * frame_period_ms
                                    sf = self._create_view(
                                        record,
                                        frame_file,
                                        view_name,
                                        view_schema,
                                        timestamp=timestamp,
                                        frame_index=idx,
                                    )
                                    views_data.append((view_name, sf))
                                    frame_views_by_stem[frame_file.stem] = (view_name, sf, idx, timestamp)
                                continue

                            if isinstance(v, list):
                                if len(v) == 0:
                                    continue
                                if len(v) > 1:
                                    # create a mosaic from record images
                                    mosaic_file = mosaic(self.source_dir, split.name, v, view_name)
                                    view_file = self.source_dir / mosaic_file
                                    if not view_file.is_file():  # no split path in metadata.jsonl
                                        view_file = self.source_dir / split.name / mosaic_file
                                else:
                                    view_file = self.source_dir / Path(v[0])
                                    if not view_file.is_file():  # no split path in metadata.jsonl
                                        view_file = self.source_dir / split.name / Path(v[0])
                                if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                                    view = self._create_view(record, view_file, view_name, view_schema)
                                    views_data.append((view_name, view))
                            else:
                                view_file = self.source_dir / (
                                    Path(v) if split.name == Path(v).parts[0] else Path(split.name) / Path(v)
                                )
                                if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                                    view = self._create_view(record, view_file, view_name, view_schema)
                                    views_data.append((view_name, view))

                all_entities_data: dict[str, list[Entity]] = defaultdict(list)
                all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]] = defaultdict(list)
                all_annotations_data: dict[str, list[RecordComponent]] = defaultdict(list)
                for k, v in dataset_piece.items():
                    if k in self.entities_schema and v is not None:
                        entity_name = k
                        raw_entities_data = v
                        entity_schema = self.entities_schema.get(entity_name)
                        if entity_schema is not None:
                            entities_data, annotations_data = self._create_objects_entities(
                                record, views_data, entity_name, entity_schema, raw_entities_data
                            )

                            for name, entities in entities_data.items():
                                all_entities_data[name].extend(entities)

                            for name, annotations in annotations_data.items():
                                all_annotations_data[name].extend(annotations)

                message_table_name = canonical_table_name_for_slot("message")
                raw_messages_data = dataset_piece.get(message_table_name)
                if raw_messages_data is not None and message_table_name in self.annotations_schema:
                    annotations_data = self._create_messages(record, views_data, raw_messages_data)
                    for name, annotations in annotations_data.items():
                        all_annotations_data[name].extend(annotations)

                # Process mask annotations (CompressedRLE) from file globs
                if frame_views_by_stem:
                    self._process_mask_annotations(
                        record,
                        dataset_piece,
                        split.name,
                        frame_views_by_stem,
                        all_entities_data,
                        all_entity_dynamic_states_data,
                        all_annotations_data,
                    )
                    self._process_bbox_track_annotations(
                        record,
                        dataset_piece,
                        split.name,
                        frame_views_by_stem,
                        views_data,
                        all_entities_data,
                        all_entity_dynamic_states_data,
                        all_annotations_data,
                    )

                yield {self.record_table_name: record}

                # Group SequenceFrame views by frame_index so each yielded dict
                # contains ALL camera views for a given frame (wide-format row).
                seq_frame_groups: dict[int, dict[str, View]] = defaultdict(dict)
                other_views: list[tuple[str, View]] = []

                for view_name, view in views_data:
                    if is_sequence_frame(type(view)):
                        seq_frame_groups[view.frame_index][view_name] = view
                    else:
                        other_views.append((view_name, view))

                # Yield non-SequenceFrame views individually
                for view_name, view in other_views:
                    yield {canonical_table_name_for_schema(type(view)): view}

                # Yield SequenceFrame views grouped by frame_index
                for frame_index in sorted(seq_frame_groups.keys()):
                    grouped_views = list(seq_frame_groups[frame_index].values())
                    yield {canonical_table_name_for_schema(type(grouped_views[0])): grouped_views}

                combined_data: dict[str, list] = {}
                if all_entities_data is not None:
                    combined_data.update(all_entities_data)
                    combined_data.update(all_entity_dynamic_states_data)
                    combined_data.update(all_annotations_data)
                if combined_data:
                    yield combined_data

    def _create_record(self, **record_metadata) -> Record:
        return self.record_schema(**record_metadata)

    def _create_view(
        self,
        record: Record,
        view_file: Path,
        view_name: str,
        view_schema: type[View],
        timestamp: float = 0.0,
        frame_index: int = 0,
    ) -> View:
        if not issubclass(view_schema, View):
            raise ValueError("View schema must be a subclass of View")

        kwargs: dict = dict(
            id=view_file.stem if self.use_image_name_as_id else shortuuid.uuid(),
            record_id=record.id,
            logical_name=view_name,
        )
        if is_video(view_schema):
            # Video uses the file path (uri) rather than raw bytes
            kwargs["uri"] = view_file
        else:
            kwargs["raw_bytes"] = view_file.read_bytes()
        if is_sequence_frame(view_schema):
            kwargs["timestamp"] = timestamp
            kwargs["frame_index"] = frame_index
        return create_instance_of_schema(view_schema, **kwargs)

    def _create_messages(
        self,
        record: Record,
        views_data: list[tuple[str, View]],
        raw_messages_data: list[Any],
    ) -> dict[str, list[RecordComponent]]:
        def resolve_view_target(target_name: str | None, fallback: tuple[str, View]) -> tuple[str, View]:
            target_name = self._normalize_view_name_alias(target_name)
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
            match = re.match(r".*<image (\d)>.*", content)  # TODO image_regex as parameter
            if match is None:
                return default_target
            for m in match.groups():
                num = int(m) - 1
                if num >= 0 and num < len(view_rows):
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
            view_name, view = views_data[0]  # Only one view
            default_target = (view_name, view)
            conversation_id = shortuuid.uuid()
            message_number = 0

            for entry in conv:
                if "question" not in entry:
                    target_view_name, target_view = resolve_view_target(entry.get("view_name"), default_target)
                    annotations[canonical_table_name_for_slot("message")].append(
                        Message(
                            id=entry.get("id", shortuuid.uuid()),
                            record_id=record.id,
                            entity_ids=message_entity_ids(entry),
                            source_type=entry.get("source_type", self._default_source_type),
                            source_name=entry.get("source_name", self._default_source_name),
                            view_id=target_view.id,
                            conversation_id=entry.get("conversation_id", conversation_id),
                            number=entry.get("number", message_number),
                            user=entry.get("user", default_user),
                            type=entry.get("type", "QUESTION"),
                            content=entry.get("content", ""),
                            choices=entry.get("choices", []),
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

                target_view_name, _target_view = update_view_target(content, views_data, default_target)
                annotations[canonical_table_name_for_slot("message")].append(
                    Message(
                        id=shortuuid.uuid(),
                        record_id=record.id,
                        source_type=self._default_source_type,
                        source_name=self._default_source_name,
                        view_id=_target_view.id,
                        conversation_id=conversation_id,
                        number=message_number,
                        type="QUESTION",
                        user=question["user"],
                        content=content,
                        choices=question.get("choices", []),
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
                            source_type=self._default_source_type,
                            source_name=self._default_source_name,
                            view_id=_target_view.id,
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

    def _create_objects_entities(
        self,
        record: Record,
        views_data: list[tuple[str, View]],
        entity_name: str,
        entity_schema: type[Entity],
        entities_data: dict[str, Any],
    ) -> tuple[dict[str, list[Entity]], dict[str, list[RecordComponent]]]:
        entities: dict[str, list[Entity]] = defaultdict(list)
        annotations: dict[str, list[RecordComponent]] = defaultdict(list)

        # Resolve target view: use "view_name" if provided, otherwise fall back to first view.
        target_view_name = entities_data.pop("view_name", None) if isinstance(entities_data, dict) else None
        target_view_name = self._normalize_view_name_alias(target_view_name)
        if target_view_name is not None:
            matched = [(n, v) for n, v in views_data if n == target_view_name]
            if not matched:
                raise ValueError(f"view_name '{target_view_name}' not found in views: {[n for n, _ in views_data]}")
            view_name, view = matched[0]
        else:
            view_name, view = views_data[0]
        frame_index = view.frame_index if hasattr(view, "frame_index") else -1

        annotation_alias_map = {
            "bbox": canonical_table_name_for_slot("bbox"),
            "mask": canonical_table_name_for_slot("mask"),
            "keypoint": canonical_table_name_for_slot("keypoint"),
        }
        for source_attr, target_attr in annotation_alias_map.items():
            if source_attr in entities_data and target_attr in self.schemas and target_attr not in entities_data:
                entities_data[target_attr] = entities_data.pop(source_attr)

        entities_attrs = list(entities_data.keys())
        for attr in entities_attrs:
            if attr not in entity_schema.model_fields.keys() and attr not in self.schemas.keys():
                raise ValueError(f"Attribute {attr} not found in entity schema and is not a schema annotation.")

        # check if all list of entities data have same length
        nums_entities = {len(v) if isinstance(v, list) else 1 for v in entities_data.values() if v is not None}
        if len(nums_entities) > 1:
            raise ValueError("All list of entities data must have same length")
        elif len(nums_entities) == 0:
            return {}, {}

        num_entities = nums_entities.pop()
        entities_data = {k: v if isinstance(v, list) else [v] for k, v in entities_data.items() if v is not None}
        entities_attrs = list(entities_data.keys())

        for i in range(num_entities):
            entity = {}
            entity_annotations: dict[str, Any] = {}
            entity_id = shortuuid.uuid()
            for attr in entities_attrs:
                if entities_data[attr] is None:
                    continue

                # check if attribute is an annotation schema
                is_attr_schema = attr in self.schemas
                if is_attr_schema and not _is_annotation(self.schemas[attr]):
                    raise ValueError(
                        f"Attribute {attr} must be an annotation schema (EntityAnnotation or EntityGroupAnnotation subclass)"
                    )

                # create annotation if attribute is an annotation schema
                if is_attr_schema:
                    if attr not in entity_annotations:
                        entity_annotations[attr] = []

                    schema = self.schemas[attr]
                    if isinstance(entities_data[attr][i], Mapping):
                        annotation = create_instance_of_schema(
                            schema,
                            id=shortuuid.uuid(),
                            record_id=record.id,
                            view_id=view.id,
                            frame_id=view.id,
                            frame_index=frame_index,
                            entity_id=entity_id,
                            source_type=self._default_source_type,
                            source_name=self._default_source_name,
                            **entities_data[attr][i],
                        )
                    else:
                        # TODO check jsonl format for mask & keypoints
                        if is_bbox(schema, True):
                            annotation = create_bbox(
                                id=shortuuid.uuid(),
                                record_id=record.id,
                                view_id=view.id,
                                frame_id=view.id,
                                frame_index=frame_index,
                                entity_id=entity_id,
                                source_type=self._default_source_type,
                                source_name=self._default_source_name,
                                coords=entities_data[attr][i],
                                format="xywh",
                                is_normalized=all(0 <= x <= 1 for x in entities_data[attr][i]),
                                confidence=1.0,
                            )
                        else:
                            raise ValueError(f"Schema {schema} not supported for infered entity creation.")
                    entity_annotations[attr].append(annotation)
                else:
                    entity[attr] = entities_data[attr][i]
            entities[entity_name].append(
                entity_schema(
                    id=entity_id,
                    record_id=record.id,
                    **entity,
                )
            )

            for key, entity_annotation in entity_annotations.items():
                annotations[key].extend(entity_annotation)
        return entities, annotations

    def _resolve_tracking_entity_schema(self) -> tuple[str | None, type[Entity] | None]:
        """Resolve the entity schema used for auto-generated temporal objects."""
        candidates = [(name, schema) for name, schema in self.entities_schema.items()]
        if not candidates:
            return None, None

        preferred_names = (canonical_table_name_for_slot("entity"), "entity")
        for preferred_name in preferred_names:
            for name, schema in candidates:
                if name == preferred_name:
                    return name, schema
        return candidates[0]

    def _resolve_entity_dynamic_state_schema(self) -> tuple[str | None, type[EntityDynamicState] | None]:
        """Resolve the dynamic state schema used for generated temporal states."""
        if not self.entity_dynamic_states_schema:
            return None, None

        preferred_names = (canonical_table_name_for_slot("entity_dynamic_state"), "entity_dynamic_state")
        for preferred_name in preferred_names:
            if preferred_name in self.entity_dynamic_states_schema:
                return preferred_name, self.entity_dynamic_states_schema[preferred_name]

        state_name = next(iter(self.entity_dynamic_states_schema))
        return state_name, self.entity_dynamic_states_schema[state_name]

    def _create_tracking_entity(
        self,
        record: Record,
        entity_schema: type[Entity],
        object_id: int,
        category: str = "",
    ) -> Entity:
        """Create one entity row for a tracked object ID."""
        kwargs: dict[str, Any] = {
            "id": shortuuid.uuid(),
            "record_id": record.id,
        }
        if "name" in entity_schema.model_fields:
            kwargs["name"] = f"object_{object_id}"
        if "category" in entity_schema.model_fields:
            kwargs["category"] = category or "object"
        return entity_schema(**kwargs)

    def _create_entity_dynamic_state(
        self,
        state_schema: type[EntityDynamicState],
        *,
        record_id: str,
        entity_id: str,
        tracklet_id: str,
        view_id: str,
        frame_id: str,
        frame_index: int,
    ) -> EntityDynamicState:
        """Create one dynamic state row linked to an entity/frame."""
        return state_schema(
            id=shortuuid.uuid(),
            record_id=record_id,
            entity_id=entity_id,
            tracklet_id=tracklet_id,
            source_type=self._default_source_type,
            source_name=self._default_source_name,
            view_id=view_id,
            frame_id=frame_id,
            frame_index=frame_index,
        )

    def _process_mask_annotations(
        self,
        record: Record,
        dataset_piece: dict,
        split_name: str,
        frame_views_by_stem: dict[str, tuple[str, View, int, float]],
        all_entities_data: dict[str, list[Entity]],
        all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]],
        all_annotations_data: dict[str, list[RecordComponent]],
    ) -> None:
        """Process mask annotation keys (CompressedRLE) from file glob patterns.

        Reads mask PNGs with indexed pixel values (0=background, N=object_N),
        creates per-object binary masks, entities, optional dynamic states,
        and optional tracklets.
        """
        for annotation_key, annotation_schema in self.annotations_schema.items():
            if not is_compressed_rle(annotation_schema):
                continue

            raw_value = dataset_piece.get(annotation_key)
            if raw_value is None:
                continue

            # Only process glob patterns / file paths, not pre-built annotation data
            if not isinstance(raw_value, str):
                continue
            if not any(c in raw_value for c in ("*", "?", "[")):
                continue

            # Expand glob pattern to get mask files
            mask_files = sorted((self.source_dir / split_name).glob(raw_value))
            if not mask_files:
                mask_files = sorted(self.source_dir.glob(raw_value))
            if not mask_files:
                continue

            # Read all mask PNGs and discover unique object IDs
            frame_masks: list[tuple[np.ndarray, str, View, int, float]] = []
            all_object_ids: set[int] = set()

            for mask_file in mask_files:
                frame_info = frame_views_by_stem.get(mask_file.stem)
                if frame_info is None:
                    continue  # No matching frame for this mask
                view_name, view, frame_index, timestamp = frame_info

                mask_img = PIL.Image.open(mask_file)
                mask_array = np.array(mask_img)

                unique_ids = set(np.unique(mask_array).tolist())
                unique_ids.discard(0)  # Remove background
                all_object_ids.update(unique_ids)

                frame_masks.append((mask_array, view_name, view, frame_index, timestamp))

            if not all_object_ids:
                continue

            entity_name, entity_schema = self._resolve_tracking_entity_schema()
            state_name, state_schema = self._resolve_entity_dynamic_state_schema()
            tracklet_table_name = canonical_table_name_for_slot("tracklet")
            has_tracklets = tracklet_table_name in self.annotations_schema

            # Create one entity per unique object ID.
            object_entities: dict[int, Entity] = {}
            for obj_id in sorted(all_object_ids):
                if entity_name is None or entity_schema is None:
                    break
                entity = self._create_tracking_entity(
                    record,
                    entity_schema=entity_schema,
                    object_id=obj_id,
                )
                all_entities_data[entity_name].append(entity)
                object_entities[obj_id] = entity

            object_tracklet_ids = {
                obj_id: shortuuid.uuid()
                for obj_id in sorted(all_object_ids)
                if has_tracklets and obj_id in object_entities
            }

            # Collect per-object frame appearances for tracklet creation
            object_appearances: dict[int, list[tuple[int, float]]] = defaultdict(list)

            # Create CompressedRLE masks per (object_id, frame)
            for mask_array, view_name, view, frame_index, timestamp in frame_masks:
                for obj_id in sorted(all_object_ids):
                    binary_mask = (mask_array == obj_id).astype(np.uint8)
                    if binary_mask.sum() == 0:
                        continue  # Object not present in this frame

                    object_appearances[obj_id].append((frame_index, timestamp))

                    entity = object_entities.get(obj_id)
                    entity_id = entity.id if entity else ""
                    tracklet_id = object_tracklet_ids.get(obj_id, "")
                    entity_dynamic_state_id = ""

                    if state_name is not None and state_schema is not None and entity is not None:
                        entity_dynamic_state = self._create_entity_dynamic_state(
                            state_schema,
                            record_id=record.id,
                            entity_id=entity.id,
                            tracklet_id=tracklet_id,
                            view_id=view.id,
                            frame_id=view.id,
                            frame_index=frame_index,
                        )
                        all_entity_dynamic_states_data[state_name].append(entity_dynamic_state)
                        entity_dynamic_state_id = entity_dynamic_state.id

                    rle = CompressedRLE.from_mask(
                        binary_mask,
                        id=shortuuid.uuid(),
                        record_id=record.id,
                        view_id=view.id,
                        frame_id=view.id,
                        frame_index=frame_index,
                        entity_id=entity_id,
                        source_type=self._default_source_type,
                        source_name=self._default_source_name,
                        tracklet_id=tracklet_id,
                        entity_dynamic_state_id=entity_dynamic_state_id,
                    )
                    all_annotations_data[annotation_key].append(rle)

            # Create Tracklets
            if has_tracklets:
                seq_view_name = frame_masks[0][1]  # view_name shared by all frames
                for obj_id, appearances in object_appearances.items():
                    entity = object_entities.get(obj_id)
                    if entity is None:
                        continue
                    appearances.sort()
                    start_idx, start_ts = appearances[0]
                    end_idx, end_ts = appearances[-1]

                    tracklet = Tracklet(
                        id=object_tracklet_ids.get(obj_id, shortuuid.uuid()),
                        record_id=record.id,
                        view_name=seq_view_name,
                        entity_id=entity.id,
                        source_type=self._default_source_type,
                        source_name=self._default_source_name,
                        start_frame=start_idx,
                        end_frame=end_idx,
                        start_timestamp=start_ts,
                        end_timestamp=end_ts,
                    )
                    all_annotations_data[tracklet_table_name].append(tracklet)

    def _process_bbox_track_annotations(
        self,
        record: Record,
        dataset_piece: dict,
        split_name: str,
        frame_views_by_stem: dict[str, tuple[str, View, int, float]],
        views_data: list[tuple[str, View]],
        all_entities_data: dict[str, list[Entity]],
        all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]],
        all_annotations_data: dict[str, list[RecordComponent]],
    ) -> None:
        """Process bbox track annotations from per-frame JSON files.

        Reads JSON files containing bounding boxes with track IDs, creates
        entities, BBox annotations per frame, optional dynamic states,
        and optional tracklet annotations.
        """
        for annotation_key, annotation_schema in self.annotations_schema.items():
            if not is_bbox(annotation_schema):
                continue

            raw_value = dataset_piece.get(annotation_key)
            if raw_value is None or not isinstance(raw_value, str):
                continue
            if not any(c in raw_value for c in ("*", "?", "[")):
                continue

            # Expand glob to get per-frame JSON files
            json_files = sorted((self.source_dir / split_name).glob(raw_value))
            if not json_files:
                json_files = sorted(self.source_dir.glob(raw_value))
            if not json_files:
                continue

            # Build view lookup: {view_name: {frame_index: (view_name, view)}}
            views_by_name_idx: dict[str, dict[int, tuple[str, View]]] = defaultdict(dict)
            for vname, view in views_data:
                if hasattr(view, "frame_index"):
                    views_by_name_idx[vname][view.frame_index] = (vname, view)

            # First pass: read all JSON files, collect unique (track_id, category) pairs
            file_data: list[tuple[str, dict]] = []  # (stem, parsed JSON)
            unique_tracks: dict[int, str] = {}  # track_id -> category

            for json_file in json_files:
                if json_file.suffix != ".json":
                    continue
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                file_data.append((json_file.stem, data))
                for obj in data.get("objects", []):
                    tid = obj.get("track_id")
                    if tid is not None:
                        unique_tracks.setdefault(tid, obj.get("category", ""))

            if not unique_tracks:
                continue

            entity_name, entity_schema = self._resolve_tracking_entity_schema()
            state_name, state_schema = self._resolve_entity_dynamic_state_schema()
            tracklet_table_name = canonical_table_name_for_slot("tracklet")
            has_tracklets = tracklet_table_name in self.annotations_schema

            # Create one entity row per unique track_id.
            object_entities: dict[int, Entity] = {}
            if entity_name is not None and entity_schema is not None:
                for tid in sorted(unique_tracks.keys()):
                    entity = self._create_tracking_entity(
                        record,
                        entity_schema=entity_schema,
                        object_id=tid,
                        category=unique_tracks[tid],
                    )
                    all_entities_data[entity_name].append(entity)
                    object_entities[tid] = entity

            object_tracklet_ids = {
                tid: shortuuid.uuid() for tid in unique_tracks if has_tracklets and tid in object_entities
            }

            # Collect per-object frame appearances for tracklet creation
            object_appearances: dict[int, list[tuple[int, float]]] = defaultdict(list)

            # Second pass: create BBox annotations per frame
            for stem, data in file_data:
                frame_info = frame_views_by_stem.get(stem)
                if frame_info is None:
                    continue

                _view_name_default, _view_default, frame_index, timestamp = frame_info
                target_view_name = self._normalize_view_name_alias(data.get("view_name"))

                for obj in data.get("objects", []):
                    tid = obj.get("track_id")
                    coords = obj.get("bbox")
                    if tid is None or coords is None:
                        continue

                    # Resolve target view for this annotation
                    if target_view_name and target_view_name in views_by_name_idx:
                        frame_view = views_by_name_idx[target_view_name].get(frame_index)
                        if frame_view is not None:
                            target_view_name, target_view = frame_view
                        else:
                            target_view_name, target_view = _view_name_default, _view_default
                    else:
                        target_view_name, target_view = _view_name_default, _view_default

                    entity = object_entities.get(tid)
                    entity_id = entity.id if entity else ""
                    tracklet_id = object_tracklet_ids.get(tid, "")
                    entity_dynamic_state_id = ""

                    if state_name is not None and state_schema is not None and entity is not None:
                        entity_dynamic_state = self._create_entity_dynamic_state(
                            state_schema,
                            record_id=record.id,
                            entity_id=entity.id,
                            tracklet_id=tracklet_id,
                            view_id=target_view.id,
                            frame_id=target_view.id,
                            frame_index=frame_index,
                        )
                        all_entity_dynamic_states_data[state_name].append(entity_dynamic_state)
                        entity_dynamic_state_id = entity_dynamic_state.id

                    bbox = create_bbox(
                        id=shortuuid.uuid(),
                        coords=coords,
                        format="xywh",
                        is_normalized=all(0 <= x <= 1 for x in coords),
                        confidence=1.0,
                        record_id=record.id,
                        view_id=target_view.id,
                        frame_id=target_view.id,
                        frame_index=frame_index,
                        entity_id=entity_id,
                        source_type=self._default_source_type,
                        source_name=self._default_source_name,
                        tracklet_id=tracklet_id,
                        entity_dynamic_state_id=entity_dynamic_state_id,
                    )
                    all_annotations_data[annotation_key].append(bbox)
                    object_appearances[tid].append((frame_index, timestamp))

            # Create Tracklets
            if has_tracklets:
                for tid, appearances in object_appearances.items():
                    entity = object_entities.get(tid)
                    if entity is None:
                        continue
                    appearances.sort()
                    start_idx, start_ts = appearances[0]
                    end_idx, end_ts = appearances[-1]

                    seq_view_name = self._normalize_view_name_alias(
                        file_data[0][1].get("view_name", _view_name_default) if file_data else _view_name_default
                    )

                    tracklet = Tracklet(
                        id=object_tracklet_ids.get(tid, shortuuid.uuid()),
                        record_id=record.id,
                        view_name=seq_view_name,
                        entity_id=entity.id,
                        source_type=self._default_source_type,
                        source_name=self._default_source_name,
                        start_frame=start_idx,
                        end_frame=end_idx,
                        start_timestamp=start_ts,
                        end_timestamp=end_ts,
                    )
                    all_annotations_data[tracklet_table_name].append(tracklet)

    def _read_metadata(self, metadata_file: Path) -> list[dict]:
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file {metadata_file} not found")
        return pa_json.read_json(metadata_file).to_pylist()

    def _build_default_custom_metadata_record(self) -> dict[str, Any]:
        custom_record_metadata: dict[str, Any] = {}
        custom_fields = list(set(self.record_schema.field_names()) - set(Record.field_names()))
        for field in custom_fields:
            field_type = self.record_schema.__annotations__[field]
            custom_record_metadata[field] = field_type()
        return custom_record_metadata


def extract_video_frames(
    video_path: Path, format: str = "JPEG", quality: int = 85
) -> Iterator[tuple[int, float, bytes]]:
    """Extract frames from a video as compressed image bytes.

    Args:
        video_path: Path to the video file.
        format: Output image format (e.g., "JPEG", "PNG").
        quality: JPEG quality (1-100). Only used for JPEG format.

    Yields:
        Tuples of (frame_index, timestamp_seconds, image_bytes).
    """
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # fallback
    idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        encode_params = []
        if format.upper() == "JPEG":
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buffer = cv2.imencode(f".{format.lower()}", frame, encode_params)
        yield idx, idx / fps, buffer.tobytes()
        idx += 1
    cap.release()
