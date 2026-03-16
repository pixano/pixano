# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import PIL.Image
import shortuuid

from pixano.schemas import (
    CompressedRLE,
    Entity,
    EntityDynamicState,
    Record,
    RecordComponent,
    Tracklet,
    View,
    canonical_table_name_for_slot,
    create_bbox,
    is_bbox,
)
from pixano.schemas.annotations.compressed_rle import is_compressed_rle

from .factories import AnnotationSource


@dataclass(frozen=True)
class TemporalSchemaResolver:
    """Resolve schemas used by temporal annotation processors."""

    entities_schema: dict[str, type[Entity]]
    entity_dynamic_states_schema: dict[str, type[EntityDynamicState]]

    def resolve_tracking_entity_schema(self) -> tuple[str | None, type[Entity] | None]:
        """Resolve the entity schema used for auto-generated temporal objects."""
        candidates = list(self.entities_schema.items())
        if not candidates:
            return None, None

        preferred_names = (canonical_table_name_for_slot("entity"), "entity")
        for preferred_name in preferred_names:
            for name, schema in candidates:
                if name == preferred_name:
                    return name, schema
        return candidates[0]

    def resolve_entity_dynamic_state_schema(self) -> tuple[str | None, type[EntityDynamicState] | None]:
        """Resolve the dynamic state schema used for generated temporal states."""
        if not self.entity_dynamic_states_schema:
            return None, None

        preferred_names = (canonical_table_name_for_slot("entity_dynamic_state"), "entity_dynamic_state")
        for preferred_name in preferred_names:
            if preferred_name in self.entity_dynamic_states_schema:
                return preferred_name, self.entity_dynamic_states_schema[preferred_name]

        state_name = next(iter(self.entity_dynamic_states_schema))
        return state_name, self.entity_dynamic_states_schema[state_name]


class TemporalRowFactory:
    """Create temporal entities and states for folder processors."""

    def __init__(self, source: AnnotationSource) -> None:
        """Initialize the factory with annotation source metadata."""
        self.source = source

    def create_tracking_entity(
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

    def create_entity_dynamic_state(
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
            source_type=self.source.source_type,
            source_name=self.source.source_name,
            view_id=view_id,
            frame_id=frame_id,
            frame_index=frame_index,
        )


class MaskTrackProcessor:
    """Import compressed-RLE masks from per-frame indexed mask files."""

    def __init__(
        self,
        *,
        source_dir: Path,
        annotations_schema: dict[str, type[RecordComponent]],
        schema_resolver: TemporalSchemaResolver,
        row_factory: TemporalRowFactory,
    ) -> None:
        """Initialize the mask track processor with source directory and schemas."""
        self.source_dir = source_dir
        self.annotations_schema = annotations_schema
        self.schema_resolver = schema_resolver
        self.row_factory = row_factory

    def process(
        self,
        *,
        record: Record,
        dataset_piece: dict[str, Any],
        split_name: str,
        frame_views_by_stem: dict[str, tuple[str, View, int, float]],
        all_entities_data: dict[str, list[Entity]],
        all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]],
        all_annotations_data: dict[str, list[RecordComponent]],
    ) -> None:
        """Populate temporal rows from mask glob annotations."""
        for annotation_key, annotation_schema in self.annotations_schema.items():
            if not is_compressed_rle(annotation_schema):
                continue

            raw_value = dataset_piece.get(annotation_key)
            if raw_value is None or not isinstance(raw_value, str):
                continue
            if not any(c in raw_value for c in ("*", "?", "[")):
                continue

            mask_files = sorted((self.source_dir / split_name).glob(raw_value))
            if not mask_files:
                mask_files = sorted(self.source_dir.glob(raw_value))
            if not mask_files:
                continue

            frame_masks: list[tuple[np.ndarray, str, View, int, float]] = []
            all_object_ids: set[int] = set()

            for mask_file in mask_files:
                frame_info = frame_views_by_stem.get(mask_file.stem)
                if frame_info is None:
                    continue
                view_name, view, frame_index, timestamp = frame_info

                mask_img = PIL.Image.open(mask_file)
                mask_array = np.array(mask_img)

                unique_ids = set(np.unique(mask_array).tolist())
                unique_ids.discard(0)
                all_object_ids.update(unique_ids)
                frame_masks.append((mask_array, view_name, view, frame_index, timestamp))

            if not all_object_ids:
                continue

            entity_name, entity_schema = self.schema_resolver.resolve_tracking_entity_schema()
            state_name, state_schema = self.schema_resolver.resolve_entity_dynamic_state_schema()
            tracklet_table_name = canonical_table_name_for_slot("tracklet")
            has_tracklets = tracklet_table_name in self.annotations_schema

            object_entities: dict[int, Entity] = {}
            for obj_id in sorted(all_object_ids):
                if entity_name is None or entity_schema is None:
                    break
                entity = self.row_factory.create_tracking_entity(record, entity_schema=entity_schema, object_id=obj_id)
                all_entities_data[entity_name].append(entity)
                object_entities[obj_id] = entity

            object_tracklet_ids = {
                obj_id: shortuuid.uuid()
                for obj_id in sorted(all_object_ids)
                if has_tracklets and obj_id in object_entities
            }
            object_appearances: dict[int, list[tuple[int, float]]] = defaultdict(list)

            for mask_array, _view_name, view, frame_index, timestamp in frame_masks:
                for obj_id in sorted(all_object_ids):
                    binary_mask = (mask_array == obj_id).astype(np.uint8)
                    if binary_mask.sum() == 0:
                        continue

                    object_appearances[obj_id].append((frame_index, timestamp))
                    entity = object_entities.get(obj_id)  # type: ignore[assignment]
                    entity_id = entity.id if entity else ""
                    tracklet_id = object_tracklet_ids.get(obj_id, "")
                    entity_dynamic_state_id = ""

                    if state_name is not None and state_schema is not None and entity is not None:
                        entity_dynamic_state = self.row_factory.create_entity_dynamic_state(
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
                        source_type=self.row_factory.source.source_type,
                        source_name=self.row_factory.source.source_name,
                        tracklet_id=tracklet_id,
                        entity_dynamic_state_id=entity_dynamic_state_id,
                    )
                    all_annotations_data[annotation_key].append(rle)

            if has_tracklets and frame_masks:
                seq_view_name = frame_masks[0][1]
                for obj_id, appearances in object_appearances.items():
                    entity = object_entities.get(obj_id)  # type: ignore[assignment]
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
                        source_type=self.row_factory.source.source_type,
                        source_name=self.row_factory.source.source_name,
                        start_timestep=start_idx,
                        end_timestep=end_idx,
                        start_timestamp=start_ts,
                        end_timestamp=end_ts,
                    )
                    all_annotations_data[tracklet_table_name].append(tracklet)


class BBoxTrackProcessor:
    """Import bbox tracks from per-frame JSON files."""

    def __init__(
        self,
        *,
        source_dir: Path,
        annotations_schema: dict[str, type[RecordComponent]],
        schema_resolver: TemporalSchemaResolver,
        row_factory: TemporalRowFactory,
        normalize_view_name_alias,
    ) -> None:
        """Initialize the bbox track processor with source directory and schemas."""
        self.source_dir = source_dir
        self.annotations_schema = annotations_schema
        self.schema_resolver = schema_resolver
        self.row_factory = row_factory
        self.normalize_view_name_alias = normalize_view_name_alias

    def process(
        self,
        *,
        record: Record,
        dataset_piece: dict[str, Any],
        split_name: str,
        frame_views_by_stem: dict[str, tuple[str, View, int, float]],
        views_data: list[tuple[str, View]],
        all_entities_data: dict[str, list[Entity]],
        all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]],
        all_annotations_data: dict[str, list[RecordComponent]],
    ) -> None:
        """Populate temporal rows from bbox track JSON annotations."""
        for annotation_key, annotation_schema in self.annotations_schema.items():
            if not is_bbox(annotation_schema):
                continue

            raw_value = dataset_piece.get(annotation_key)
            if raw_value is None or not isinstance(raw_value, str):
                continue
            if not any(c in raw_value for c in ("*", "?", "[")):
                continue

            json_files = sorted((self.source_dir / split_name).glob(raw_value))
            if not json_files:
                json_files = sorted(self.source_dir.glob(raw_value))
            if not json_files:
                continue

            views_by_name_idx: dict[str, dict[int, tuple[str, View]]] = defaultdict(dict)
            for view_name, view in views_data:
                if hasattr(view, "frame_index"):
                    views_by_name_idx[view_name][view.frame_index] = (view_name, view)

            file_data: list[tuple[str, dict]] = []
            unique_tracks: dict[int, str] = {}

            for json_file in json_files:
                if json_file.suffix != ".json":
                    continue
                with open(json_file, encoding="utf-8") as handle:
                    data = json.load(handle)
                file_data.append((json_file.stem, data))
                for obj in data.get("objects", []):
                    track_id = obj.get("track_id")
                    if track_id is not None:
                        unique_tracks.setdefault(track_id, obj.get("category", ""))

            if not unique_tracks:
                continue

            entity_name, entity_schema = self.schema_resolver.resolve_tracking_entity_schema()
            state_name, state_schema = self.schema_resolver.resolve_entity_dynamic_state_schema()
            tracklet_table_name = canonical_table_name_for_slot("tracklet")
            has_tracklets = tracklet_table_name in self.annotations_schema

            object_entities: dict[int, Entity] = {}
            if entity_name is not None and entity_schema is not None:
                for track_id in sorted(unique_tracks.keys()):
                    entity = self.row_factory.create_tracking_entity(
                        record,
                        entity_schema=entity_schema,
                        object_id=track_id,
                        category=unique_tracks[track_id],
                    )
                    all_entities_data[entity_name].append(entity)
                    object_entities[track_id] = entity

            object_tracklet_ids = {
                track_id: shortuuid.uuid()
                for track_id in unique_tracks
                if has_tracklets and track_id in object_entities
            }
            object_appearances: dict[int, list[tuple[int, float]]] = defaultdict(list)

            default_view_name = ""
            for stem, data in file_data:
                frame_info = frame_views_by_stem.get(stem)
                if frame_info is None:
                    continue

                default_view_name, default_view, frame_index, timestamp = frame_info
                target_view_name = self.normalize_view_name_alias(data.get("view_name"))

                for obj in data.get("objects", []):
                    track_id = obj.get("track_id")
                    coords = obj.get("bbox")
                    if track_id is None or coords is None:
                        continue

                    if target_view_name and target_view_name in views_by_name_idx:
                        frame_view = views_by_name_idx[target_view_name].get(frame_index)
                        if frame_view is not None:
                            _resolved_name, target_view = frame_view
                        else:
                            target_view = default_view
                    else:
                        target_view = default_view

                    entity = object_entities.get(track_id)  # type: ignore[assignment]
                    entity_id = entity.id if entity else ""
                    tracklet_id = object_tracklet_ids.get(track_id, "")
                    entity_dynamic_state_id = ""

                    if state_name is not None and state_schema is not None and entity is not None:
                        entity_dynamic_state = self.row_factory.create_entity_dynamic_state(
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
                        source_type=self.row_factory.source.source_type,
                        source_name=self.row_factory.source.source_name,
                        tracklet_id=tracklet_id,
                        entity_dynamic_state_id=entity_dynamic_state_id,
                    )
                    all_annotations_data[annotation_key].append(bbox)
                    object_appearances[track_id].append((frame_index, timestamp))

            if has_tracklets:
                for track_id, appearances in object_appearances.items():
                    entity = object_entities.get(track_id)  # type: ignore[assignment]
                    if entity is None:
                        continue
                    appearances.sort()
                    start_idx, start_ts = appearances[0]
                    end_idx, end_ts = appearances[-1]

                    seq_view_name = self.normalize_view_name_alias(
                        file_data[0][1].get("view_name", default_view_name) if file_data else default_view_name
                    )

                    tracklet = Tracklet(
                        id=object_tracklet_ids.get(track_id, shortuuid.uuid()),
                        record_id=record.id,
                        view_name=seq_view_name,
                        entity_id=entity.id,
                        source_type=self.row_factory.source.source_type,
                        source_name=self.row_factory.source.source_name,
                        start_timestep=start_idx,
                        end_timestep=end_idx,
                        start_timestamp=start_ts,
                        end_timestamp=end_ts,
                    )
                    all_annotations_data[tracklet_table_name].append(tracklet)
