# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The single strict JSONL v2 parser, shared by analyze and ingest (spec §5).

One ``json.loads`` per line — the preflight-vs-build divergence of the v1
folder import (two different JSON parsers) is structurally gone. Every
problem becomes a :class:`~pixano.datasets.io.plan.Finding` with
``file:line:json-pointer`` provenance and a did-you-mean suggestion; invalid
lines are reported, never guessed at.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from pydantic import ValidationError

from pixano.datasets.dataset_info import DatasetInfo

from ...plan import PreflightReport, Provenance
from ...spec import _KIND_BY_VIEW
from .spec import (
    HEADER_KEY,
    KNOWN_KINDS,
    RESERVED_KINDS,
    TOP_LEVEL_KEYS,
    VIEW_PAYLOAD_MODELS,
    HeaderDefaults,
    HeaderLine,
    LineModel,
)


# Top-level keys of the v1 metadata.jsonl dialect: their presence means the
# file needs `pixano data migrate-jsonl`, not guessing.
_V1_MARKER_KEYS = frozenset({"objects", "object", "view", "messages", "status"})

_MIGRATE_HINT = "This looks like the 0.7.x metadata.jsonl dialect; run `pixano data migrate-jsonl` to convert it."


def view_kinds_of(info: DatasetInfo) -> dict[str, str]:
    """Map an info's logical view names to their JSONL v2 view kinds."""
    kinds: dict[str, str] = {}
    for logical_name, view_cls in info.views.items():
        base = next((b for b in view_cls.__mro__ if b in _KIND_BY_VIEW), None)
        if base is not None:
            kinds[logical_name] = _KIND_BY_VIEW[base]
    return kinds


@dataclass
class ParsedLine:
    """One validated record line with its effective defaults and provenance."""

    line_number: int
    split: str
    model: LineModel
    views: dict[str, Any]  # logical name -> validated per-kind view payload model
    defaults: HeaderDefaults
    provenance: Provenance


def _suggest(unknown: str, known: Any) -> str:
    matches = difflib.get_close_matches(unknown, list(known), n=1)
    return f" Did you mean '{matches[0]}'?" if matches else ""


def _validation_error_findings(exc: ValidationError, report: PreflightReport, path: Path, line_number: int) -> None:
    for error in exc.errors():
        pointer = "/" + "/".join(str(loc) for loc in error["loc"]) if error["loc"] else ""
        provenance = Provenance(file=str(path), line=line_number, json_pointer=pointer or None)
        if error["type"] == "extra_forbidden":
            unknown = str(error["loc"][-1])
            if unknown in _V1_MARKER_KEYS:
                report.add("v1_format", provenance, suggestion=_MIGRATE_HINT)
            else:
                report.add(
                    "unknown_key",
                    provenance,
                    suggestion=f"'{unknown}' is not part of the JSONL v2 grammar.{_suggest(unknown, TOP_LEVEL_KEYS)}",
                )
        elif error["type"] == "union_tag_invalid" or (
            error["loc"] and error["loc"][-1] == "kind" and error["type"].startswith("literal")
        ):
            raw_input = error.get("input")
            kind = raw_input.get("kind") if isinstance(raw_input, dict) else raw_input
            if isinstance(kind, str) and kind in RESERVED_KINDS:
                report.add(
                    "reserved_kind",
                    provenance,
                    suggestion=f"Annotation kind '{kind}' is reserved for a later release and cannot be imported yet.",
                )
            else:
                report.add(
                    "unknown_kind",
                    provenance,
                    suggestion=f"Unknown annotation kind {kind!r}.{_suggest(str(kind), KNOWN_KINDS)}",
                )
        else:
            report.add(
                "invalid_value",
                provenance,
                suggestion=f"{error['msg']} (at {pointer or '<line>'})",
            )


def _validate_views(
    raw_views: dict[str, Any],
    view_kinds: dict[str, str],
    report: PreflightReport,
    path: Path,
    line_number: int,
) -> dict[str, Any] | None:
    validated: dict[str, Any] = {}
    ok = True
    for view_name, raw_value in raw_views.items():
        provenance = Provenance(file=str(path), line=line_number, json_pointer=f"/views/{view_name}")
        kind = view_kinds.get(view_name)
        if kind is None:
            report.add(
                "undeclared_view",
                provenance,
                suggestion=f"View '{view_name}' is not declared in the schema.{_suggest(view_name, view_kinds)}",
            )
            ok = False
            continue
        payload_model = VIEW_PAYLOAD_MODELS[kind]
        payload = {"uri": raw_value} if isinstance(raw_value, str) and kind == "image" else raw_value
        if not isinstance(payload, dict):
            report.add(
                "invalid_view_payload",
                provenance,
                suggestion=f"View '{view_name}' (kind '{kind}') expects an object payload.",
            )
            ok = False
            continue
        try:
            validated[view_name] = payload_model.model_validate(payload)
        except ValidationError as exc:
            _validation_error_findings(exc, report, path, line_number)
            ok = False
    return validated if ok else None


def _check_line_semantics(
    model: LineModel,
    view_kinds: dict[str, str],
    defaults: HeaderDefaults,
    report: PreflightReport,
    path: Path,
    line_number: int,
) -> bool:
    ok = True
    multi_view = len(view_kinds) > 1

    for entity_index, entity in enumerate(model.entities):
        for ann_index, annotation in enumerate(entity.annotations):
            pointer = f"/entities/{entity_index}/annotations/{ann_index}"
            provenance = Provenance(file=str(path), line=line_number, json_pointer=pointer)
            if annotation.view is None and multi_view:
                report.add(
                    "view_required",
                    provenance,
                    suggestion="The schema declares several views: every annotation needs a 'view'.",
                )
                ok = False
            elif annotation.view is not None and annotation.view not in view_kinds:
                report.add(
                    "undeclared_view",
                    provenance,
                    suggestion=f"View '{annotation.view}' is not declared.{_suggest(annotation.view, view_kinds)}",
                )
                ok = False
            if annotation.kind == "bbox":
                effective_format = annotation.format or defaults.bbox.format
                effective_normalized = (
                    annotation.is_normalized if annotation.is_normalized is not None else defaults.bbox.is_normalized
                )
                if effective_format is None or effective_normalized is None:
                    report.add(
                        "bbox_defaults_required",
                        provenance,
                        suggestion=(
                            "bbox 'format' and 'is_normalized' are required — set them on the annotation "
                            "or in the header defaults (coordinates are never guessed from value ranges)."
                        ),
                    )
                    ok = False
        for tracklet_index, tracklet in enumerate(entity.tracklets):
            if tracklet.view not in view_kinds:
                report.add(
                    "undeclared_view",
                    Provenance(
                        file=str(path),
                        line=line_number,
                        json_pointer=f"/entities/{entity_index}/tracklets/{tracklet_index}",
                    ),
                    suggestion=f"View '{tracklet.view}' is not declared.{_suggest(tracklet.view, view_kinds)}",
                )
                ok = False

    for conversation_index, conversation in enumerate(model.conversations):
        for message_index, message in enumerate(conversation.messages):
            if message.type == "QUESTION" and not message.question_type:
                report.add(
                    "question_type_required",
                    Provenance(
                        file=str(path),
                        line=line_number,
                        json_pointer=f"/conversations/{conversation_index}/messages/{message_index}",
                    ),
                    suggestion="QUESTION messages must declare a 'question_type'.",
                )
                ok = False

    for sidecar_index, sidecar in enumerate(model.annotation_files):
        if sidecar.view not in view_kinds:
            report.add(
                "undeclared_view",
                Provenance(file=str(path), line=line_number, json_pointer=f"/annotation_files/{sidecar_index}"),
                suggestion=f"View '{sidecar.view}' is not declared.{_suggest(sidecar.view, view_kinds)}",
            )
            ok = False

    return ok


def parse_file(
    path: Path,
    split: str,
    view_kinds: dict[str, str],
    report: PreflightReport,
    max_lines: int | None = None,
) -> Iterator[ParsedLine]:
    """Stream-parse one metadata.jsonl file, yielding only fully valid lines.

    Invalid lines produce findings in ``report`` and are skipped — analyze and
    ingest run the exact same code, so what was validated is what imports.
    """
    defaults = HeaderDefaults()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if max_lines is not None and line_number > max_lines:
                return
            stripped = raw_line.strip()
            if not stripped:
                continue
            provenance = Provenance(file=str(path), line=line_number)
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                report.add("invalid_json", provenance, suggestion=str(exc))
                continue
            if not isinstance(payload, dict):
                report.add("invalid_line", provenance, suggestion="Each line must be a JSON object.")
                continue

            if HEADER_KEY in payload:
                if line_number != 1:
                    report.add("header_not_first", provenance, suggestion="The $pixano header must be line 1.")
                    continue
                try:
                    defaults = HeaderLine.model_validate(payload).defaults
                except ValidationError as exc:
                    _validation_error_findings(exc, report, path, line_number)
                continue

            try:
                model = LineModel.model_validate(payload)
            except ValidationError as exc:
                _validation_error_findings(exc, report, path, line_number)
                continue

            views = _validate_views(model.views, view_kinds, report, path, line_number)
            if views is None:
                continue
            if not _check_line_semantics(model, view_kinds, defaults, report, path, line_number):
                continue

            yield ParsedLine(
                line_number=line_number,
                split=model.split or split,
                model=model,
                views=views,
                defaults=defaults,
                provenance=provenance,
            )
