# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Best-effort converter from the 0.7.x metadata.jsonl dialect to JSONL v2 (spec §12).

Freezes the v1 alias/shape rules as a one-way rewrite. Ambiguities the v1
parser resolved by guessing (value-range normalization sniffing, bare
``[start, end]`` text spans) are converted with an explicit note in the
report instead of silently. Frozen after 0.8.0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_V1_ENTITY_KEYS = ("entities", "objects", "object")
_V1_VIEW_SHORTHAND_KEYS = ("image", "view")
_KNOWN_TOP_LEVEL = {"id", "views", "annotation_files", "messages", "fps"}


@dataclass
class MigrationReport:
    """Outcome of one migration run."""

    files_migrated: int = 0
    lines_migrated: int = 0
    needs_attention: list[str] = field(default_factory=list)


def migrate_tree(source: Path, destination: Path) -> MigrationReport:
    """Convert every ``<split>/metadata.jsonl`` under ``source`` into ``destination``."""
    report = MigrationReport()
    for metadata_file in sorted(source.glob("*/metadata.jsonl")):
        split = metadata_file.parent.name
        target_file = destination / split / "metadata.jsonl"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with metadata_file.open(encoding="utf-8") as reader, target_file.open("w", encoding="utf-8") as writer:
            writer.write(
                json.dumps({"$pixano": "jsonl/2", "defaults": {"bbox": {"format": "xywh", "is_normalized": True}}})
                + "\n"
            )
            for line_number, raw_line in enumerate(reader, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                location = f"{split}/metadata.jsonl:{line_number}"
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    report.needs_attention.append(f"{location}: invalid JSON ({exc})")
                    continue
                migrated = migrate_line(payload, location, report)
                writer.write(json.dumps(migrated, ensure_ascii=False) + "\n")
                report.lines_migrated += 1
        report.files_migrated += 1
    return report


def migrate_line(payload: dict[str, Any], location: str, report: MigrationReport) -> dict[str, Any]:
    """Convert one v1 line to the v2 grammar."""
    source = dict(payload)
    line: dict[str, Any] = {}
    attrs: dict[str, Any] = {}

    if "id" in source:
        line["id"] = source.pop("id")

    views = _migrate_views(source, location, report)
    line["views"] = views

    entities = _migrate_entities(source, views, location, report)
    if entities:
        line["entities"] = entities

    conversations = _migrate_messages(source, location, report)
    if conversations:
        line["conversations"] = conversations

    sidecars = _migrate_annotation_files(source, views, location, report)
    if sidecars:
        line["annotation_files"] = sidecars

    source.pop("fps", None)  # folded into the view payload
    for key, value in source.items():
        attrs[key] = value  # v1 spilled record fields at top level (e.g. status)
    if attrs:
        line["attrs"] = attrs
    return line


def _is_glob(value: str) -> bool:
    return any(character in value for character in "*?[")


def _migrate_views(source: dict[str, Any], location: str, report: MigrationReport) -> dict[str, Any]:
    raw_views = source.pop("views", None) or {}
    for shorthand in _V1_VIEW_SHORTHAND_KEYS:
        if shorthand in source and isinstance(source[shorthand], (str, list)):
            raw_views.setdefault("image", source.pop(shorthand))

    top_level_fps = source.get("fps")
    views: dict[str, Any] = {}
    for view_name, value in raw_views.items():
        if isinstance(value, list):
            if len(value) == 1:
                value = value[0]
            else:
                report.needs_attention.append(
                    f"{location}: view '{view_name}' held {len(value)} files (v1 built a mosaic); kept the first."
                )
                value = value[0] if value else ""
        if isinstance(value, dict):
            path = value.get("path", "")
            fps = value.get("fps", top_level_fps)
            if _is_glob(str(path)):
                views[view_name] = {"frame_pattern": path, "fps": fps or 24}
                if fps is None:
                    report.needs_attention.append(
                        f"{location}: no fps for '{view_name}'; defaulted to 24 (v1 default)."
                    )
            else:
                views[view_name] = str(path)
        elif isinstance(value, str):
            if _is_glob(value):
                views[view_name] = {"frame_pattern": value, "fps": top_level_fps or 24}
            elif value.endswith(".txt"):
                views[view_name] = {"uri": value}  # v1 text views referenced .txt files
            elif " " in value or not Path(value).suffix:
                # v1 docs showed inline sentences as text views; v2 makes it explicit.
                views[view_name] = {"content": value}
                report.needs_attention.append(
                    f"{location}: view '{view_name}' value treated as inline text content; verify."
                )
            else:
                views[view_name] = value
    return views


def _migrate_entities(
    source: dict[str, Any], views: dict[str, Any], location: str, report: MigrationReport
) -> list[dict[str, Any]]:
    raw_entities = None
    for key in _V1_ENTITY_KEYS:
        if key in source:
            raw_entities = source.pop(key)
            break
    if not isinstance(raw_entities, list):
        return []

    single_view = next(iter(views), "")
    entities: list[dict[str, Any]] = []
    for entry in raw_entities:
        if not isinstance(entry, dict):
            report.needs_attention.append(f"{location}: non-object entity entry dropped.")
            continue
        entry = dict(entry)
        annotations_by_view = entry.pop("annotations", {}) or {}
        entity: dict[str, Any] = {}
        if entry:
            entity["attrs"] = entry
        annotations: list[dict[str, Any]] = []
        for view_name, group in annotations_by_view.items():
            if not isinstance(group, dict):
                continue
            for kind_key, value in group.items():
                annotation = _migrate_annotation(kind_key, value, view_name or single_view, location, report)
                if annotation is not None:
                    annotations.append(annotation)
        if annotations:
            entity["annotations"] = annotations
        entities.append(entity)
    return entities


def _migrate_annotation(
    kind_key: str, value: Any, view_name: str, location: str, report: MigrationReport
) -> dict[str, Any] | None:
    base = {"view": view_name} if view_name else {}
    if kind_key in ("bbox", "bboxes"):
        if isinstance(value, list):
            normalized = all(isinstance(coord, (int, float)) and 0 <= coord <= 1 for coord in value)
            if not normalized:
                report.needs_attention.append(
                    f"{location}: bbox normalization inferred from value ranges (v1 behavior); verify."
                )
            return {"kind": "bbox", **base, "coords": value, "format": "xywh", "is_normalized": normalized}
        if isinstance(value, dict):
            return {
                "kind": "bbox",
                **base,
                "coords": value.get("coords", []),
                "format": value.get("format", "xywh"),
                "is_normalized": bool(value.get("is_normalized", True)),
                "confidence": value.get("confidence", 1.0),
            }
    if kind_key in ("keypoint", "keypoints"):
        if isinstance(value, dict):
            return {
                "kind": "keypoints",
                **base,
                "template_id": value.get("template_id", ""),
                "coords": value.get("coords", []),
                "states": value.get("states", []),
            }
    if kind_key in ("mask", "masks"):
        if isinstance(value, dict) and "size" in value and "counts" in value:
            return {"kind": "mask", **base, "rle": {"size": value["size"], "counts": value["counts"]}}
    if kind_key in ("text_span", "text_spans"):
        if isinstance(value, dict):
            return {
                "kind": "text_span",
                **base,
                "mention": value.get("mention", ""),
                "spans_start": value.get("spans_start", []),
                "spans_end": value.get("spans_end", []),
            }
        if isinstance(value, list) and len(value) == 2:
            report.needs_attention.append(
                f"{location}: text_span [start, end] has no mention; migrated with an empty one — fill it in."
            )
            return {"kind": "text_span", **base, "mention": "", "spans_start": [value[0]], "spans_end": [value[1]]}
    report.needs_attention.append(f"{location}: unsupported v1 annotation '{kind_key}' dropped.")
    return None


def _migrate_messages(source: dict[str, Any], location: str, report: MigrationReport) -> list[dict[str, Any]]:
    raw = source.pop("messages", None) or source.pop("conversations", None)
    if not isinstance(raw, list) or not raw:
        return []

    messages: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if "question" in entry:
            question = entry.get("question") or {}
            message = {
                "type": "QUESTION",
                "content": question.get("content", ""),
                "question_type": str(question.get("question_type", "OPEN")).upper(),
            }
            if question.get("choices"):
                message["choices"] = question["choices"]
            messages.append(message)
            responses = entry.get("responses") or entry.get("response") or []
            if isinstance(responses, dict):
                responses = [responses]
            for response in responses:
                messages.append({"type": "ANSWER", "content": (response or {}).get("content", "")})
        elif "type" in entry:
            message = {"type": str(entry.get("type", "")).upper(), "content": entry.get("content", "")}
            if message["type"] == "QUESTION":
                message["question_type"] = str(entry.get("question_type", "OPEN")).upper()
            if entry.get("choices"):
                message["choices"] = entry["choices"]
            if entry.get("user"):
                message["user"] = entry["user"]
            messages.append(message)
        else:
            report.needs_attention.append(f"{location}: unrecognized message entry dropped.")
    return [{"messages": messages}] if messages else []


def _migrate_annotation_files(
    source: dict[str, Any], views: dict[str, Any], location: str, report: MigrationReport
) -> list[dict[str, Any]]:
    raw = source.pop("annotation_files", None)
    if not isinstance(raw, dict):
        return []
    single_view = next(iter(views), "")
    sidecars: list[dict[str, Any]] = []
    for kind_key, value in raw.items():
        pattern = value.get("path") if isinstance(value, dict) else value
        if not isinstance(pattern, str):
            continue
        if kind_key == "mask":
            sidecars.append(
                {
                    "kind": "mask",
                    "view": single_view,
                    "pattern": pattern,
                    "encoding": "index_png",
                    "entity_map": "auto",
                }
            )
        elif kind_key == "bbox":
            sidecars.append({"kind": "bbox", "view": single_view, "pattern": pattern, "encoding": "track_json"})
            report.needs_attention.append(
                f"{location}: track_json bboxes assume normalized xywh (header defaults); verify."
            )
        else:
            report.needs_attention.append(f"{location}: unsupported annotation_files kind '{kind_key}' dropped.")
    return sidecars
