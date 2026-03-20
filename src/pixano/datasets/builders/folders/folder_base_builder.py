# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

import pyarrow.json as pa_json
import shortuuid
from lancedb.pydantic import LanceModel

from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.builders.validators import ViewFamilyIntegrityValidator
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.utils import mosaic
from pixano.datasets.workspaces import WorkspaceType
from pixano.features.utils.creators import create_instance_of_schema
from pixano.schemas import (
    Entity,
    EntityDynamicState,
    Record,
    RecordComponent,
    View,
    canonical_table_name_for_schema,
    canonical_table_name_for_slot,
    is_sequence_frame,
    is_text,
    is_video,
)
from pixano.schemas.annotations.entity_annotation import AnnotationSourceKind

from .factories import AnnotationSource, FolderEntityFactory, FolderMessageFactory, FolderRecordFactory
from .metadata import FolderMetadataService, MetadataValidationReport
from .processors import BBoxTrackProcessor, MaskTrackProcessor, TemporalRowFactory, TemporalSchemaResolver


class FolderBaseBuilder(DatasetBuilder):
    """This is a class for building datasets based on a folder structure.

    The folder structure should be as follows:
        - source_dir/{split}/{item}.{ext}
        - source_dir/{split}/metadata.jsonl

    The metadata file should be a jsonl file with the following canonical format:
    ```json
        [
            {
                "id": "item1",
                "views": {
                    "image": "item1.jpg"
                },
                "entities": [
                    {
                        "category": "person",
                        "annotations": {
                            "image": {
                                "bbox": [0.1, 0.1, 0.2, 0.3]
                            }
                        }
                    }
                ]
            },
            ...
        ]
    ```

    Note:
        Multiple views are supported through the top-level ``views`` mapping. Entity annotations are attached
        per view under ``entities[].annotations.<view_name>``.
        If you give a list of images for a single view field, they will be put in a mosaic.

    Attributes:
        source_dir: The source directory for the dataset.
        METADATA_FILENAME: The metadata filename.
        EXTENSIONS: The list of supported extensions.
        DEFAULT_INFO: Default dataset schema and workspace for the builder.
    """

    METADATA_FILENAME: str = "metadata.jsonl"
    EXTENSIONS: list[str]
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
        expected_workspace = self._expected_workspace()
        if expected_workspace is not None and info.workspace != expected_workspace:
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

        self._view_family_validator = ViewFamilyIntegrityValidator(self.schemas)
        self._source_context = AnnotationSource(
            source_type=AnnotationSourceKind.OTHER.value,
            source_name="Builder",
        )
        self._record_factory = FolderRecordFactory(self.record_schema)
        self._metadata_service = FolderMetadataService(
            source_dir=self.source_dir,
            metadata_filename=self.METADATA_FILENAME,
            record_field_names=set(self.record_schema.model_fields.keys()),
            views_schema=self.views_schema,
            entities_schema=self.entities_schema,
            entity_dynamic_states_schema=self.entity_dynamic_states_schema,
            annotations_schema=self.annotations_schema,
            resolve_view_files=self._resolve_view_files,
        )
        self._message_factory = FolderMessageFactory(
            source=self._source_context,
            normalize_view_name_alias=self._metadata_service.normalize_view_name_alias,
        )
        self._entity_factory = FolderEntityFactory(
            schemas=self.schemas,
            source=self._source_context,
            normalize_view_name_alias=self._metadata_service.normalize_view_name_alias,
        )
        temporal_schema_resolver = TemporalSchemaResolver(
            entities_schema=self.entities_schema,
            entity_dynamic_states_schema=self.entity_dynamic_states_schema,
        )
        temporal_row_factory = TemporalRowFactory(source=self._source_context)
        self._mask_track_processor = MaskTrackProcessor(
            source_dir=self.source_dir,
            annotations_schema=self.annotations_schema,
            schema_resolver=temporal_schema_resolver,
            row_factory=temporal_row_factory,
        )
        self._bbox_track_processor = BBoxTrackProcessor(
            source_dir=self.source_dir,
            annotations_schema=self.annotations_schema,
            schema_resolver=temporal_schema_resolver,
            row_factory=temporal_row_factory,
            normalize_view_name_alias=self._metadata_service.normalize_view_name_alias,
        )

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

    def _expected_workspace(self) -> WorkspaceType | None:
        """Return the workspace declared by the builder default dataset info."""
        if self.DEFAULT_INFO is None:
            return None
        return self.DEFAULT_INFO.workspace

    @staticmethod
    def _normalize_metadata_key(key: str) -> str:
        return FolderMetadataService.normalize_metadata_key(key)

    @staticmethod
    def _is_media_path_token(value: str) -> bool:
        return FolderMetadataService.is_media_path_token(value)

    def _matches_single_view_payload(self, value: Any) -> bool:
        """Check if a metadata value can be routed to the single declared view field."""
        return self._metadata_service._matches_single_view_payload(value)

    def _matches_entity_payload(self, entity_name: str, value: Any) -> bool:
        """Check if a metadata value matches a declared entity field."""
        return self._metadata_service._matches_entity_payload(entity_name, value)

    def _matches_entity_dynamic_state_payload(self, state_name: str, value: Any) -> bool:
        """Check if a metadata value matches a declared entity dynamic state field."""
        return self._metadata_service._matches_entity_dynamic_state_payload(state_name, value)

    def _resolve_schema_key_from_value(self, value: Any) -> str | None:
        """Resolve an unknown metadata key from payload shape using declared schema only."""
        return self._metadata_service.resolve_schema_key_from_value(value)

    def _normalize_dataset_piece_keys(self, dataset_piece: dict[str, Any]) -> dict[str, Any]:
        """Normalize metadata keys to schema field names when mapping is unambiguous."""
        return self._metadata_service.normalize_dataset_piece(dataset_piece)

    def _normalize_dataset_piece_keys_with_report(
        self,
        dataset_piece: dict[str, Any],
        report: MetadataValidationReport | None,
        split_name: str,
        line_number: int,
        validation_mode: str,
    ) -> dict[str, Any]:
        """Normalize metadata keys and update the validation report."""
        return self._metadata_service.normalize_dataset_piece_with_report(
            dataset_piece,
            report,
            split_name,
            line_number,
            validation_mode,
        )

    def _metadata_alias_map(self) -> dict[str, str]:
        """Return accepted metadata aliases for the current dataset schema."""
        return self._metadata_service.metadata_alias_map()

    def _normalize_view_name_alias(self, view_name: str | None) -> str | None:
        """Resolve a metadata view alias to its declared logical name."""
        return self._metadata_service.normalize_view_name_alias(view_name)

    def _resolve_view_files(self, split_name: str, raw_value: Any, view_schema: type[View]) -> list[Path]:
        """Resolve a metadata view payload into concrete file paths."""
        split_dir = self.source_dir / split_name
        if is_sequence_frame(view_schema):
            return self._resolve_sequence_frame_files(split_dir, raw_value)

        if isinstance(raw_value, list):
            if len(raw_value) == 0:
                return []
            if len(raw_value) > 1:
                return self._resolve_list_files(split_dir, raw_value)
            raw_value = raw_value[0]

        if isinstance(raw_value, str):
            path = self._resolve_single_path(split_name, raw_value)
            return [path] if path.is_file() else []
        return []

    def _resolve_non_sequence_view_file(self, split_name: str, raw_value: Any, view_name: str) -> Path | None:
        """Resolve the effective file for a non-sequence view payload."""
        split_dir = self.source_dir / split_name
        if isinstance(raw_value, list):
            if len(raw_value) == 0:
                return None
            if len(raw_value) > 1:
                mosaic_file = mosaic(self.source_dir, split_name, raw_value, view_name)
                view_file = self.source_dir / mosaic_file
                if not view_file.is_file():
                    view_file = split_dir / mosaic_file
                return view_file if view_file.is_file() else None
            raw_value = raw_value[0]
        if not isinstance(raw_value, str):
            return None
        view_file = self._resolve_single_path(split_name, raw_value)
        return view_file if view_file.is_file() else None

    def _resolve_sequence_frame_files(self, split_dir: Path, raw_value: Any) -> list[Path]:
        """Resolve sequence frame payloads into ordered frame files."""
        if isinstance(raw_value, str) and any(c in raw_value for c in ("*", "?", "[")):
            frame_files = sorted(split_dir.glob(raw_value))
            if not frame_files:
                frame_files = sorted(self.source_dir.glob(raw_value))
            return frame_files
        if isinstance(raw_value, list):
            return self._resolve_list_files(split_dir, raw_value)
        if isinstance(raw_value, str):
            path = self._resolve_single_path(split_dir.name, raw_value)
            return [path] if path.is_file() else []
        return []

    def _resolve_list_files(self, split_dir: Path, raw_values: list[Any]) -> list[Path]:
        """Resolve a list of relative media paths against source and split roots."""
        resolved_files: list[Path] = []
        for item in raw_values:
            if not isinstance(item, str):
                continue
            path = self.source_dir / Path(item)
            if not path.is_file():
                path = split_dir / Path(item)
            if path.is_file():
                resolved_files.append(path)
        return resolved_files

    def _resolve_single_path(self, split_name: str, raw_value: str) -> Path:
        """Resolve one relative media path against the source directory."""
        raw_path = Path(raw_value)
        if raw_path.parts and raw_path.parts[0] == split_name:
            return self.source_dir / raw_path
        return self.source_dir / split_name / raw_path

    def _validate_entity_payload(
        self,
        payload: dict[str, Any],
        schema: type[LanceModel],
        split_name: str,
        line_number: int,
        report: MetadataValidationReport,
        validation_mode: str,
    ) -> None:
        """Validate one entity payload from metadata."""
        self._metadata_service._validate_entity_payload(
            payload, schema, split_name, line_number, report, validation_mode
        )

    def _validate_dataset_piece(
        self,
        dataset_piece: dict[str, Any],
        split_name: str,
        line_number: int,
        report: MetadataValidationReport,
        validation_mode: str,
    ) -> None:
        """Validate one top-level metadata row."""
        self._metadata_service.validate_dataset_piece(dataset_piece, split_name, line_number, report, validation_mode)

    def preflight_metadata(self, validation_mode: str | None = None) -> MetadataValidationReport:
        """Validate all ``metadata.jsonl`` files before building the dataset."""
        mode = validation_mode or self.metadata_validation_mode
        cached_report = self._metadata_report_cache.get(mode)
        if cached_report is not None:
            return cached_report

        report = self._metadata_service.preflight_metadata(mode)
        self._metadata_report_cache[mode] = report
        return report

    def _validate_batch(self, batch: dict[str, list[LanceModel]], dataset) -> None:
        """Apply folder-specific integrity validation before inserting a batch."""
        self._view_family_validator.validate(batch, dataset)

        tracklet_table_name = canonical_table_name_for_slot("tracklet")
        for row in batch.get(tracklet_table_name, []):
            start_timestep = getattr(row, "start_timestep", -1)
            end_timestep = getattr(row, "end_timestep", -1)
            if start_timestep == -1 or end_timestep == -1:
                raise ValueError(
                    "Invalid imported tracklet: start_timestep/end_timestep must be set before insertion."
                )

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

        for split in self.source_dir.glob("*"):
            if not split.is_dir() or split.name.startswith("."):
                continue

            try:
                dataset_pieces = self._read_metadata(split / self.METADATA_FILENAME)
            except FileNotFoundError:
                dataset_pieces = None

            if dataset_pieces is None:
                yield from self._generate_data_without_metadata(split)
                continue

            for i, dataset_piece in enumerate(dataset_pieces):
                yield from self._generate_data_from_metadata(split.name, i, dataset_piece)

    def _generate_data_without_metadata(
        self,
        split: Path,
    ) -> Iterator[dict[str, LanceModel | list[LanceModel]]]:
        """Yield records and views for a split without ``metadata.jsonl``."""
        view_name, view_schema = list(self.views_schema.items())[0]
        for view_file in sorted(split.glob("**/*")):
            if not view_file.is_file() or view_file.suffix not in self.EXTENSIONS:
                continue
            record_metadata = self._build_default_custom_metadata_record()
            record_metadata["id"] = view_file.stem
            record_metadata["split"] = split.name
            record = self._create_record(**record_metadata)
            view = self._create_view(record, view_file, view_name, view_schema)
            yield {
                self.record_table_name: record,
                canonical_table_name_for_schema(view_schema): view,
            }

    def _generate_data_from_metadata(
        self,
        split_name: str,
        row_index: int,
        dataset_piece: dict[str, Any],
    ) -> Iterator[dict[str, LanceModel | list[LanceModel]]]:
        """Yield all batches generated from one metadata row."""
        normalized_piece = self._normalize_dataset_piece_keys(dict(dataset_piece))
        fps = normalized_piece.pop("fps", None)
        frame_period_ms = 1000.0 / (fps if fps is not None else 24.0)

        record_metadata = self._extract_record_metadata(normalized_piece)
        record_metadata.setdefault(
            "id",
            f"record_{split_name}_{row_index}" if self.use_image_name_as_id else shortuuid.uuid(),
        )
        record_metadata.setdefault("split", split_name)
        record = self._create_record(**record_metadata)

        views_data, frame_views_by_stem = self._create_views_for_record(
            record, split_name, normalized_piece, frame_period_ms
        )
        components = self._create_components_for_record(
            record, split_name, normalized_piece, views_data, frame_views_by_stem
        )

        yield {self.record_table_name: record}
        yield from self._yield_view_batches(views_data)
        combined_data = self._combine_component_data(*components)
        if combined_data:
            yield combined_data

    def _extract_record_metadata(self, dataset_piece: dict[str, Any]) -> dict[str, Any]:
        """Split record-level metadata from view and component payloads."""
        record_metadata = {
            key: value
            for key, value in dataset_piece.items()
            if key not in self.views_schema
            and key not in self.entities_schema
            and key not in self.entity_dynamic_states_schema
            and key not in self.annotations_schema
        }
        for key in record_metadata:
            dataset_piece.pop(key, None)
        return record_metadata

    def _create_views_for_record(
        self,
        record: Record,
        split_name: str,
        dataset_piece: dict[str, Any],
        frame_period_ms: float,
    ) -> tuple[list[tuple[str, View]], dict[str, tuple[str, View, int, float]]]:
        """Create views declared in one metadata row."""
        views_data: list[tuple[str, View]] = []
        frame_views_by_stem: dict[str, tuple[str, View, int, float]] = {}

        for view_name, raw_value in dataset_piece.items():
            if view_name not in self.views_schema:
                continue
            view_schema = self.views_schema.get(view_name)
            if view_schema is None:
                continue

            if is_sequence_frame(view_schema):
                frame_files = self._resolve_view_files(split_name, raw_value, view_schema)
                for frame_index, frame_file in enumerate(frame_files):
                    if frame_file.suffix not in self.EXTENSIONS:
                        continue
                    timestamp = frame_index * frame_period_ms
                    view = self._create_view(
                        record,
                        frame_file,
                        view_name,
                        view_schema,
                        timestamp=timestamp,
                        frame_index=frame_index,
                    )
                    views_data.append((view_name, view))
                    frame_views_by_stem[frame_file.stem] = (view_name, view, frame_index, timestamp)
                continue

            view_file = self._resolve_non_sequence_view_file(split_name, raw_value, view_name)
            if view_file is None or view_file.suffix not in self.EXTENSIONS:
                continue
            views_data.append((view_name, self._create_view(record, view_file, view_name, view_schema)))

        return views_data, frame_views_by_stem

    def _create_components_for_record(
        self,
        record: Record,
        split_name: str,
        dataset_piece: dict[str, Any],
        views_data: list[tuple[str, View]],
        frame_views_by_stem: dict[str, tuple[str, View, int, float]],
    ) -> tuple[
        dict[str, list[Entity]],
        dict[str, list[EntityDynamicState]],
        dict[str, list[RecordComponent]],
    ]:
        """Create entities, states, and annotations for one metadata row."""
        all_entities_data: dict[str, list[Entity]] = defaultdict(list)
        all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]] = defaultdict(list)
        all_annotations_data: dict[str, list[RecordComponent]] = defaultdict(list)

        for entity_name, raw_entities_data in dataset_piece.items():
            if entity_name not in self.entities_schema or raw_entities_data is None:
                continue
            if not isinstance(raw_entities_data, list):
                raise ValueError(f"Entity payload for '{entity_name}' must be a list of entity objects.")
            entity_schema = self.entities_schema.get(entity_name)
            if entity_schema is None:
                continue
            entities_data, annotations_data = self._create_objects_entities(
                record,
                views_data,
                entity_name,
                entity_schema,
                raw_entities_data,
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

        if frame_views_by_stem:
            self._process_mask_annotations(
                record,
                dataset_piece,
                split_name,
                frame_views_by_stem,
                all_entities_data,
                all_entity_dynamic_states_data,
                all_annotations_data,
            )
            self._process_bbox_track_annotations(
                record,
                dataset_piece,
                split_name,
                frame_views_by_stem,
                views_data,
                all_entities_data,
                all_entity_dynamic_states_data,
                all_annotations_data,
            )

        return all_entities_data, all_entity_dynamic_states_data, all_annotations_data

    def _yield_view_batches(
        self, views_data: list[tuple[str, View]]
    ) -> Iterator[dict[str, LanceModel | list[LanceModel]]]:
        """Yield views in the same batch layout expected by the dataset builder."""
        seq_frame_groups: dict[int, dict[str, View]] = defaultdict(dict)
        other_views: list[tuple[str, View]] = []

        for view_name, view in views_data:
            if is_sequence_frame(type(view)):
                seq_frame_groups[view.frame_index][view_name] = view
            else:
                other_views.append((view_name, view))

        for _view_name, view in other_views:
            yield {canonical_table_name_for_schema(type(view)): view}

        for frame_index in sorted(seq_frame_groups.keys()):
            grouped_views = list(seq_frame_groups[frame_index].values())
            yield {canonical_table_name_for_schema(type(grouped_views[0])): grouped_views}

    def _combine_component_data(self, *data_groups: dict[str, list[Any]]) -> dict[str, list[Any]]:
        """Merge multiple component dictionaries while preserving table grouping."""
        combined_data: dict[str, list[Any]] = {}
        for data_group in data_groups:
            combined_data.update(data_group)
        return combined_data

    def _create_record(self, **record_metadata) -> Record:
        """Create one record row from normalized metadata."""
        return self._record_factory.create_record(**record_metadata)

    def _create_view(
        self,
        record: Record,
        view_file: Path,
        view_name: str,
        view_schema: type[View],
        timestamp: float = 0.0,
        frame_index: int = 0,
    ) -> View:
        """Create one view row from a resolved media file."""
        if not issubclass(view_schema, View):
            raise ValueError("View schema must be a subclass of View")

        kwargs: dict[str, Any] = {
            "id": view_file.stem if self.use_image_name_as_id else shortuuid.uuid(),
            "record_id": record.id,
            "logical_name": view_name,
        }
        if is_text(view_schema):
            kwargs["content"] = view_file.read_text(encoding="utf-8")
            kwargs["uri"] = str(view_file)
        elif is_video(view_schema):
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
        """Create message annotations from normalized metadata."""
        return self._message_factory.create_messages(record, views_data, raw_messages_data)

    def _create_objects_entities(
        self,
        record: Record,
        views_data: list[tuple[str, View]],
        entity_name: str,
        entity_schema: type[Entity],
        entities_data: list[dict[str, Any]],
    ) -> tuple[dict[str, list[Entity]], dict[str, list[RecordComponent]]]:
        """Create entities and their attached annotations from metadata."""
        return self._entity_factory.create_objects_entities(
            record, views_data, entity_name, entity_schema, entities_data
        )

    def _resolve_tracking_entity_schema(self) -> tuple[str | None, type[Entity] | None]:
        """Resolve the entity schema used for auto-generated temporal objects."""
        return self._bbox_track_processor.schema_resolver.resolve_tracking_entity_schema()

    def _resolve_entity_dynamic_state_schema(self) -> tuple[str | None, type[EntityDynamicState] | None]:
        """Resolve the dynamic state schema used for generated temporal states."""
        return self._bbox_track_processor.schema_resolver.resolve_entity_dynamic_state_schema()

    def _create_tracking_entity(
        self,
        record: Record,
        entity_schema: type[Entity],
        object_id: int,
        category: str = "",
    ) -> Entity:
        """Create one entity row for a tracked object ID."""
        return self._bbox_track_processor.row_factory.create_tracking_entity(
            record, entity_schema, object_id, category
        )

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
        return self._bbox_track_processor.row_factory.create_entity_dynamic_state(
            state_schema,
            record_id=record_id,
            entity_id=entity_id,
            tracklet_id=tracklet_id,
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
        """Process mask annotation keys (CompressedRLE) from file glob patterns."""
        self._mask_track_processor.process(
            record=record,
            dataset_piece=dataset_piece,
            split_name=split_name,
            frame_views_by_stem=frame_views_by_stem,
            all_entities_data=all_entities_data,
            all_entity_dynamic_states_data=all_entity_dynamic_states_data,
            all_annotations_data=all_annotations_data,
        )

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
        """Process bbox track annotations from per-frame JSON files."""
        self._bbox_track_processor.process(
            record=record,
            dataset_piece=dataset_piece,
            split_name=split_name,
            frame_views_by_stem=frame_views_by_stem,
            views_data=views_data,
            all_entities_data=all_entities_data,
            all_entity_dynamic_states_data=all_entity_dynamic_states_data,
            all_annotations_data=all_annotations_data,
        )

    def _read_metadata(self, metadata_file: Path) -> list[dict]:
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file {metadata_file} not found")
        return pa_json.read_json(metadata_file).to_pylist()

    def _build_default_custom_metadata_record(self) -> dict[str, Any]:
        """Create default values for custom record fields."""
        return self._record_factory.build_default_custom_metadata_record()


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
