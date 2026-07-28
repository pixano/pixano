# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""JSONL v2 exporter: emits exactly the import grammar (spec §5/§10).

Export output *is* valid import input by construction — ids are explicit, so
import → export → import is id-equal (the CI round-trip contract). Media
policy ``files`` dumps embedded bytes to relative paths beside the JSONL
(incrementally, never accumulated); ``uris`` writes stored URIs verbatim and
fails with guidance on embedded-only datasets.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from lancedb.pydantic import LanceModel

from pixano.datasets.dataset import Dataset
from pixano.schemas import Entity, EntityDynamicState, Record
from pixano.schemas.annotations.entity_annotation import EntityAnnotation
from pixano.schemas.annotations.per_frame_annotation import PerFrameAnnotation

from ...errors import SpecValidationError
from ...reader import RecordBundle, RecordBundleReader
from ...spec import SchemaSpec
from .spec import HEADER_KEY


_RECORD_BASE_FIELDS = set(Record.model_fields)
_ENTITY_BASE_FIELDS = set(Entity.model_fields)
_EDS_BASE_FIELDS = set(EntityDynamicState.model_fields)

_ANNOTATION_TABLE_KINDS = {
    "bboxes": "bbox",
    "masks": "mask",
    "keypoints": "keypoints",
    "multi_paths": "multi_path",
    "text_spans": "text_span",
    "classifications": "classification",
}

# Fields that are part of the annotation payload schema (not custom attrs).
_ANN_KNOWN_FIELDS: dict[str, set[str]] = {
    "bbox": {"coords", "format", "is_normalized", "confidence"},
    "mask": {"rle", "polygons", "size", "counts"},
    "keypoints": {"template_id", "coords", "states"},
    "multi_path": {"coords", "num_points", "is_closed"},
    "text_span": {"mention", "spans_start", "spans_end"},
    "classification": {"labels", "confidences"},
}

_ANN_BASE_FIELDS = set(EntityAnnotation.model_fields)
_PFA_BASE_FIELDS = set(PerFrameAnnotation.model_fields)

# Per-frame annotation kinds carry extra temporal fields that must be excluded.
_PFA_KINDS = {"bbox", "mask", "keypoints", "multi_path"}


def _json_default(obj: Any) -> Any:
    """JSON serializer fallback for non-serializable types (datetime, etc.)."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class PixanoJsonlExporter:
    """Streams a dataset back to the JSONL v2 folder layout."""

    def __init__(
        self,
        media: Literal["files", "uris"] = "files",
        reader: RecordBundleReader | None = None,
        *,
        options: dict[str, Any] | None = None,
    ):
        """Configure the export media policy."""
        self.media = media
        self.reader = reader or RecordBundleReader()
        self.options = options or {}

    def export(self, dataset: Dataset, destination: Path) -> Path:
        """Export the dataset; returns the destination directory."""
        destination.mkdir(parents=True, exist_ok=True)
        self._write_spec_yaml(dataset, destination)

        handles: dict[str, Any] = {}
        try:
            for bundle in self.reader.iter_bundles(dataset):
                split = bundle.record.split
                if split not in handles:
                    split_dir = destination / split
                    split_dir.mkdir(parents=True, exist_ok=True)
                    handles[split] = (split_dir / "metadata.jsonl").open("w", encoding="utf-8")
                    handles[split].write(json.dumps({HEADER_KEY: "jsonl/2"}) + "\n")
                line = self._bundle_to_line(bundle, destination / split)
                handles[split].write(json.dumps(line, ensure_ascii=False, default=_json_default) + "\n")
        finally:
            for handle in handles.values():
                handle.close()
        return destination

    # ------------------------------------------------------------------
    # dataset.yaml
    # ------------------------------------------------------------------

    def _write_spec_yaml(self, dataset: Dataset, destination: Path) -> None:
        spec_payload: dict[str, Any] = {
            "pixano": 2,
            "dataset": {"name": dataset.info.name, "workspace": dataset.info.workspace.value},
            "format": "pixano_jsonl",
            "media": {"mode": "uri" if self.media == "uris" else "embed"},
        }
        include_fields = self.options.get("include_record_fields")
        if include_fields:
            # Recorded under `options` so the exported dataset.yaml stays a VALID
            # import spec (ImportSpec forbids unknown top-level keys); the key is
            # inert on import and documents how the export was produced.
            spec_payload["options"] = {"include_record_fields": list(include_fields)}
        try:
            schema = SchemaSpec.from_dataset_info(dataset.info)
            spec_payload["schema"] = schema.model_dump(exclude_defaults=True, exclude_none=True)
        except SpecValidationError:
            from pixano.datasets.dataset_schema import _serialize_table_schema

            manifest: dict[str, Any] = {"views": {}}
            for slot_name, schema_cls in dataset.info.tables.items():
                if slot_name == "records":
                    manifest["record"] = _serialize_table_schema(schema_cls)
            for logical_name, view_cls in dataset.info.views.items():
                manifest["views"][logical_name] = _serialize_table_schema(view_cls)
            spec_payload["schema_manifest"] = manifest
        (destination / "dataset.yaml").write_text(yaml.safe_dump(spec_payload, sort_keys=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # Row -> line reverse mapping
    # ------------------------------------------------------------------

    def _bundle_to_line(self, bundle: RecordBundle, split_dir: Path) -> dict[str, Any]:
        line: dict[str, Any] = {"id": bundle.record_id}

        # Compute which record base fields to exclude from attrs.
        # Always exclude id/split (handled at the line level), but optionally
        # include status, created_at, updated_at, comment when requested.
        include = set(self.options.get("include_record_fields", []))
        exclude = _RECORD_BASE_FIELDS - include
        exclude |= {"id", "split"}

        attrs = dict(bundle.record.model_dump(exclude=exclude))
        if attrs:
            line["attrs"] = attrs

        view_id_to_logical: dict[str, str] = {}
        views: dict[str, Any] = {}
        sequence_frames: dict[str, list[LanceModel]] = {}
        for table_name in ("images", "videos", "sequence_frames", "texts", "point_clouds"):
            for row in bundle.components.get(table_name, []):
                view_id_to_logical[row.id] = row.logical_name
                if table_name == "sequence_frames":
                    sequence_frames.setdefault(row.logical_name, []).append(row)
                else:
                    views[row.logical_name] = self._view_payload(table_name, row, split_dir)
        for logical_name, frames in sequence_frames.items():
            frames.sort(key=lambda row: row.frame_index)
            views[logical_name] = {
                "frames": [
                    {
                        "uri": self._media_ref(row, split_dir, logical_name),
                        "frame_index": row.frame_index,
                        "timestamp": row.timestamp,
                    }
                    for row in frames
                ]
            }
        line["views"] = views

        entities = self._entities_payload(bundle, view_id_to_logical)
        if entities:
            line["entities"] = entities

        conversations = self._conversations_payload(bundle, view_id_to_logical)
        if conversations:
            line["conversations"] = conversations
        return line

    def _view_payload(self, table_name: str, row: LanceModel, split_dir: Path) -> dict[str, Any]:
        if table_name == "texts":
            return {"content": row.content} if row.content else {"uri": row.uri}
        payload: dict[str, Any] = {"uri": self._media_ref(row, split_dir, row.logical_name)}
        if table_name == "images":
            payload.update(width=row.width, height=row.height)
        elif table_name == "videos":
            payload.update(fps=row.fps, from_timestamp=row.from_timestamp, to_timestamp=row.to_timestamp)
        return payload

    def _media_ref(self, row: LanceModel, split_dir: Path, logical_name: str) -> str:
        raw_bytes = getattr(row, "raw_bytes", b"")
        uri = getattr(row, "uri", "")
        if raw_bytes:
            if self.media == "uris":
                raise SpecValidationError(
                    "media='uris' cannot export embedded media; use media='files' to dump bytes beside the JSONL."
                )
            extension = (getattr(row, "format", "") or "bin").lower()
            relative = Path("media") / logical_name / f"{row.id}.{extension}"
            target = split_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw_bytes)
            return str(relative)
        return uri

    def _entities_payload(self, bundle: RecordBundle, view_id_to_logical: dict[str, str]) -> list[dict[str, Any]]:
        entities: dict[str, dict[str, Any]] = {}
        for row in bundle.components.get("entities", []):
            entity: dict[str, Any] = {"id": row.id}
            if row.parent_id:
                entity["parent_id"] = row.parent_id
            attrs = row.model_dump(exclude=_ENTITY_BASE_FIELDS)
            if attrs:
                entity["attrs"] = attrs
            entities[row.id] = entity

        for table_name, kind in _ANNOTATION_TABLE_KINDS.items():
            for row in bundle.components.get(table_name, []):
                target = entities.get(row.entity_id)
                if target is None:
                    continue
                target.setdefault("annotations", []).append(self._annotation_payload(kind, row, view_id_to_logical))

        for row in bundle.components.get("tracklets", []):
            target = entities.get(row.entity_id)
            if target is None:
                continue
            view = view_id_to_logical.get(row.view_id) or next(iter(view_id_to_logical.values()), "")
            target.setdefault("tracklets", []).append(
                {
                    "id": row.id,
                    "view": view,
                    "start_timestep": row.start_timestep,
                    "end_timestep": row.end_timestep,
                    "start_timestamp": row.start_timestamp,
                    "end_timestamp": row.end_timestamp,
                }
            )

        for row in bundle.components.get("entity_dynamic_states", []):
            target = entities.get(row.entity_id)
            if target is None:
                continue
            state: dict[str, Any] = {"frame_index": row.frame_index}
            state_attrs = row.model_dump(exclude=_EDS_BASE_FIELDS)
            if state_attrs:
                state["attrs"] = state_attrs
            target.setdefault("states", []).append(state)

        return list(entities.values())

    def _annotation_payload(self, kind: str, row: LanceModel, view_id_to_logical: dict[str, str]) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": kind, "id": row.id}
        view = view_id_to_logical.get(row.view_id)
        if view:
            payload["view"] = view
        frame_index = getattr(row, "frame_index", -1)
        if frame_index is not None and frame_index >= 0:
            payload["frame_index"] = frame_index
        if row.source_type:
            payload["source"] = {"type": row.source_type, "name": row.source_name or "import"}

        if kind == "bbox":
            payload.update(
                coords=row.coords, format=row.format, is_normalized=row.is_normalized, confidence=row.confidence
            )
        elif kind == "mask":
            counts = row.counts.decode("utf-8") if isinstance(row.counts, bytes) else row.counts
            payload["rle"] = {"size": row.size, "counts": counts}
        elif kind == "keypoints":
            payload.update(template_id=row.template_id, coords=row.coords, states=row.states)
        elif kind == "multi_path":
            payload.update(coords=row.coords, num_points=row.num_points, is_closed=row.is_closed)
        elif kind == "text_span":
            payload.update(mention=row.mention, spans_start=row.spans_start, spans_end=row.spans_end)
        elif kind == "classification":
            payload.update(labels=row.labels, confidences=row.confidences)

        # Extract custom attrs (fields not in the base schema or known kind-specific fields).
        exclude = _ANN_BASE_FIELDS | _ANN_KNOWN_FIELDS.get(kind, set())
        if kind in _PFA_KINDS:
            exclude |= _PFA_BASE_FIELDS
        custom_attrs = row.model_dump(exclude=exclude, exclude_unset=True)
        if custom_attrs:
            payload["attrs"] = custom_attrs

        return payload

    def _conversations_payload(self, bundle: RecordBundle, view_id_to_logical: dict[str, str]) -> list[dict[str, Any]]:
        by_conversation: dict[str, list[LanceModel]] = {}
        for row in bundle.components.get("messages", []):
            by_conversation.setdefault(row.conversation_id, []).append(row)

        conversations = []
        for conversation_id in sorted(by_conversation):
            rows = sorted(by_conversation[conversation_id], key=lambda row: (row.number, row.id))
            messages = []
            for row in rows:
                message: dict[str, Any] = {"type": row.type, "content": row.content}
                if row.question_type:
                    message["question_type"] = row.question_type
                if row.choices:
                    message["choices"] = list(row.choices)
                if row.user:
                    message["user"] = row.user
                view = view_id_to_logical.get(row.view_id)
                if view:
                    message["views"] = [view]
                messages.append(message)
            conversations.append({"id": conversation_id, "messages": messages})
        return conversations
