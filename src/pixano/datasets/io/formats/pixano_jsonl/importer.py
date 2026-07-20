# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The pixano_jsonl importer: JSONL v2 lines → table rows (spec §7.1).

Analyze and ingest run the exact same parser; ids derive deterministically
(spec §5) so re-runs converge and resume is exact. Media resolves under the
two storage modes (§6): local paths embed, remote URIs pass through.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

from lancedb.pydantic import LanceModel
from pydantic import ValidationError

from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import canonical_table_name_for_schema, canonical_table_name_for_slot

from ...errors import MediaResolutionError, MetadataError, PixanoDataError, SpecValidationError
from ...ids import stable_id
from ...importer import BatchBundle, Cursor, DatasetImporter, DetectResult, SourceRef
from ...media import MediaResolver, ffmpeg_available, ffprobe_available, probe_image, probe_video
from ...plan import AnalyzeLimits, ImportPlan, PreflightReport, Provenance, SamplePreview
from ...registry import Capabilities, DataFormat
from ...spec import ImportSpec, resolve_dataset_info
from .media_only import (
    classify_media,
    decode_video_frames,
    discover_layout,
    folder_frames_fps,
    frame_folder_files,
    frames_mode,
    is_media_only_source,
    thumbnail_data_url,
)
from .parser import ParsedLine, parse_file, view_kinds_of
from .sidecars import decode_index_png, decode_track_json
from .spec import HEADER_KEY, EntitySpec, SidecarSpec


METADATA_FILENAME = "metadata.jsonl"


def _splits_of(source_dir: Path) -> list[Path]:
    return sorted(p for p in source_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


class _LineContext:
    """Everything needed to turn parsed lines of one split into rows."""

    def __init__(self, info: DatasetInfo, spec: ImportSpec, split_dir: Path, namespace: str):
        self.info = info
        self.spec = spec
        self.split_dir = split_dir
        self.namespace = namespace
        self.view_kinds = view_kinds_of(info)
        self.resolver = MediaResolver(spec.media, base_dir=split_dir)
        self.single_view = next(iter(self.view_kinds)) if len(self.view_kinds) == 1 else None

    def slot_schema(self, slot: str) -> type[LanceModel] | None:
        return getattr(self.info, slot, None)


class PixanoJsonlImporter(DatasetImporter):
    """Importer for the canonical JSONL v2 folder layout (spec §5/§7.1)."""

    format_name = "pixano_jsonl"
    importer_version = "1.0.0"
    supports_resume = True
    deterministic_ids = True

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def probe(self, source: SourceRef) -> DetectResult | None:
        """Sniff for dataset.yaml, a $pixano header, or split metadata.jsonl files."""
        if source.path is None or not source.path.is_dir():
            return None
        if (source.path / "dataset.yaml").is_file():
            return DetectResult(confidence=0.95, evidence="dataset.yaml at source root")
        for split_dir in _splits_of(source.path):
            metadata_file = split_dir / METADATA_FILENAME
            if metadata_file.is_file():
                first_line = metadata_file.open(encoding="utf-8").readline()
                if HEADER_KEY in first_line:
                    return DetectResult(confidence=0.95, evidence="$pixano header")
                return DetectResult(confidence=0.6, evidence=f"{split_dir.name}/{METADATA_FILENAME}")
        if is_media_only_source(source.path):
            return DetectResult(confidence=0.3, evidence="media files without metadata (media-only mode)")
        return None

    # ------------------------------------------------------------------
    # Schema resolution
    # ------------------------------------------------------------------

    def resolve_info(self, spec: ImportSpec, source: SourceRef | None = None) -> DatasetInfo:
        """Media-only sources infer their views from the folder layout; a user schema still wins."""
        declared_views = spec.schema_ is not None and bool(spec.schema_.views)
        if spec.schema_manifest is not None or declared_views:
            return resolve_dataset_info(spec)
        if source is None or source.path is None or not is_media_only_source(source.path):
            return resolve_dataset_info(spec)

        mode = frames_mode(spec)
        layout = discover_layout(source.path, None, PreflightReport(), folder_frames=mode == "folders")
        if not layout.view_kinds:
            return resolve_dataset_info(spec)

        # File kind -> view kind: video files extract to annotatable frames by
        # default (like LeRobot); "reference" keeps browse-scale Video rows;
        # pre-extracted frame folders ("frames") are sequence frames as-is.
        video_kind = "sequence_frames" if mode == "extract" else "video"
        view_kind_map = {"image": "image", "video": video_kind, "text": "text", "frames": "sequence_frames"}
        payload = spec.model_dump(mode="json", exclude_none=True, by_alias=True)
        schema_payload = dict(payload.get("schema") or {})
        schema_payload["views"] = {name: {"kind": view_kind_map[kind]} for name, kind in layout.view_kinds.items()}
        file_kinds = set(layout.view_kinds.values())
        if file_kinds == {"text"} and not schema_payload.get("annotations"):
            schema_payload["annotations"] = ["classification", "text_span"]
        payload["schema"] = schema_payload
        if payload.get("dataset", {}).get("workspace", "undefined") == "undefined":
            # Formats know their natural UI workspace; an explicit --workspace wins.
            if file_kinds & {"video", "frames"}:
                payload.setdefault("dataset", {})["workspace"] = "video"
            elif "image" in file_kinds:
                payload.setdefault("dataset", {})["workspace"] = "image"
        return resolve_dataset_info(ImportSpec.model_validate(payload))

    # ------------------------------------------------------------------
    # Analyze
    # ------------------------------------------------------------------

    def analyze(self, source: SourceRef, spec: ImportSpec, limits: AnalyzeLimits) -> ImportPlan:
        """Stream-validate every split with the ingest parser; never touch storage."""
        plan = ImportPlan(format=self.format_name, importer_version=self.importer_version)
        if source.path is None or not source.path.is_dir():
            plan.report.add("invalid_source", Provenance(file=source.location()), suggestion="Expected a directory.")
            return plan
        if is_media_only_source(source.path):
            return self._analyze_media_only(source, spec, limits, plan)

        info = self.resolve_info(spec, source)
        namespace = self.effective_namespace(spec, source)
        total_records = 0
        media_probes = 0
        truncated = False

        for split_dir in _splits_of(source.path):
            context = _LineContext(info, spec, split_dir, namespace)
            metadata_file = split_dir / METADATA_FILENAME
            split_count = 0

            if not metadata_file.is_file():
                media_files = self._media_only_files(context, plan.report, split_dir)
                split_count = len(media_files) if media_files is not None else 0
            else:
                for line in parse_file(
                    metadata_file, split_dir.name, context.view_kinds, plan.report, max_lines=limits.max_lines
                ):
                    split_count += 1
                    self._check_attrs(context, line, plan.report)
                    if media_probes < limits.max_media_probes:
                        media_probes += self._check_media(context, line, plan.report)
                    if len(plan.previews) < limits.max_previews:
                        plan.previews.append(
                            SamplePreview(record={"split": line.split, **line.model.model_dump(exclude_none=True)})
                        )
                if limits.max_lines is not None and split_count >= limits.max_lines:
                    truncated = True

            plan.splits[split_dir.name] = split_count
            total_records += split_count

        plan.totals.records = total_records
        plan.totals.estimated = truncated
        return plan

    def _analyze_media_only(
        self, source: SourceRef, spec: ImportSpec, limits: AnalyzeLimits, plan: ImportPlan
    ) -> ImportPlan:
        """Analyze a bare media folder: discover the layout, count, preview, estimate."""
        assert source.path is not None
        mode = frames_mode(spec)
        folder_frames = mode == "folders"
        if folder_frames:
            folder_frames_fps(spec)  # invalid options.fps fails analyze, not mid-ingest
        if spec.schema_manifest is not None or (spec.schema_ is not None and spec.schema_.views):
            try:
                declared = view_kinds_of(resolve_dataset_info(spec))
            except SpecValidationError as error:
                plan.report.add("invalid_spec", Provenance(file=source.location()), suggestion=str(error))
                return plan
            layout = discover_layout(source.path, declared, plan.report, folder_frames=folder_frames)
            extracts_frames = "sequence_frames" in declared.values() and not folder_frames
        else:
            # Inference: layout findings (mixed kinds, ambiguity) land in the plan.
            layout = discover_layout(source.path, None, plan.report, folder_frames=folder_frames)
            extracts_frames = "video" in layout.view_kinds.values() and mode == "extract"

        if extracts_frames and not (ffmpeg_available() and ffprobe_available()):
            plan.report.add(
                "ffmpeg_required",
                Provenance(file=source.location()),
                suggestion="Frame extraction needs ffmpeg+ffprobe on PATH; install ffmpeg or use "
                'options {"frames": "reference"}.',
            )

        self._check_media_only_record_attrs(spec, source, plan.report)
        self._probe_media_only_files(layout, limits, plan.report)
        max_frames = self._max_frames_per_video(spec)
        estimate = 0
        for split in layout.splits:
            plan.splits[split.name] = len(split.records)
            if extracts_frames and ffprobe_available():
                estimate += self._extract_size_estimate(split, layout, max_frames)
            for group in split.records:
                if len(plan.previews) >= limits.max_previews:
                    continue
                thumbnails = {}
                for view, file in sorted(group.files.items()):
                    kind = layout.view_kinds.get(view)
                    if kind == "image":
                        url = thumbnail_data_url(file)
                    elif kind == "frames":
                        frames = frame_folder_files(file)
                        url = thumbnail_data_url(frames[0]) if frames else None
                    else:
                        url = None
                    if url is not None:
                        thumbnails[view] = url
                plan.previews.append(
                    SamplePreview(
                        record={
                            "split": split.name,
                            "record": group.key,
                            **{view: file.name for view, file in sorted(group.files.items())},
                        },
                        thumbnails=thumbnails,
                    )
                )
        plan.totals.records = layout.total_records
        plan.totals.media_bytes = layout.media_bytes
        if estimate:
            plan.media_size_estimate_bytes = estimate
        return plan

    def _check_media_only_record_attrs(self, spec: ImportSpec, source: SourceRef, report: PreflightReport) -> None:
        """Media-only ingest builds records with no attr values: required record attrs can never be satisfied."""
        from pixano.schemas import Record

        try:
            info = self.resolve_info(spec, source)
        except (SpecValidationError, ValidationError):
            return  # a broken spec surfaces through its own finding/error path
        if info.record is None:
            return
        base_fields = set(Record.model_fields)
        required = sorted(
            name for name, field in info.record.model_fields.items() if name not in base_fields and field.is_required()
        )
        if required:
            report.add(
                "required_record_attr",
                Provenance(file=source.location()),
                suggestion="Media-only imports create records without attribute values; give "
                f"{', '.join(repr(name) for name in required)} a default or drop 'required'.",
            )

    @staticmethod
    def _probe_media_only_files(layout: Any, limits: AnalyzeLimits, report: PreflightReport) -> None:
        """Bounded readability probes so bad media fails analyze, not mid-ingest."""
        window = 64 * 1024
        probes = 0
        can_probe_video = ffprobe_available()
        for split in layout.splits:
            for group in split.records:
                for view, media_file in sorted(group.files.items()):
                    if probes >= limits.max_media_probes:
                        return
                    kind = layout.view_kinds.get(view)
                    if kind == "text":
                        probes += 1
                        data = media_file.read_bytes()[:window]
                        try:
                            data.decode("utf-8")
                        except UnicodeDecodeError as error:
                            if len(data) == window and error.start >= window - 4:
                                continue  # a multi-byte char cut by the probe window, not a bad file
                            report.add(
                                "unreadable_text",
                                Provenance(file=str(media_file)),
                                suggestion=f"'{media_file.name}' is not valid UTF-8; re-encode it or remove it.",
                            )
                    elif kind == "video" and can_probe_video:
                        probes += 1
                        try:
                            probe = probe_video(media_file)
                        except PixanoDataError as error:
                            report.add(
                                "unreadable_video",
                                Provenance(file=str(media_file)),
                                suggestion=f"'{media_file.name}' cannot be read as a video ({error}); "
                                "re-encode it or remove it.",
                            )
                            continue
                        if probe.num_frames <= 0:
                            report.add(
                                "unreadable_video",
                                Provenance(file=str(media_file)),
                                suggestion=f"'{media_file.name}' has no decodable frames; re-encode it or remove it.",
                            )
                    elif kind == "frames":
                        frames = frame_folder_files(media_file)
                        if not frames:
                            continue
                        probes += 1
                        try:
                            probe_image(frames[0])
                        except PixanoDataError as error:
                            report.add(
                                "unreadable_image",
                                Provenance(file=str(frames[0])),
                                suggestion=f"'{media_file.name}/{frames[0].name}' cannot be read as an image "
                                f"({error}); re-encode it or remove it.",
                            )

    @staticmethod
    def _max_frames_per_video(spec: ImportSpec) -> int:
        return int(spec.options.get("max_frames_per_video", 0) or 0)

    @staticmethod
    def _extract_size_estimate(split: Any, layout: Any, max_frames: int) -> int:
        """Rough JPEG bytes for frame extraction: probe one video per view, scale by count."""
        estimate = 0.0
        for view, kind in layout.view_kinds.items():
            if kind != "video":
                continue
            videos = [group.files[view] for group in split.records if view in group.files]
            if not videos:
                continue
            try:
                probe = probe_video(videos[0])
            except PixanoDataError:
                continue
            frames = min(probe.num_frames, max_frames) if max_frames else probe.num_frames
            estimate += len(videos) * frames * probe.width * probe.height * 0.12
        return int(estimate)

    def _media_only_files(self, context: _LineContext, report: PreflightReport, split_dir: Path) -> list[Path] | None:
        """Metadata-less splits inside a mixed JSONL source (single image view only)."""
        if context.single_view is None or context.view_kinds.get(context.single_view) != "image":
            report.add(
                "media_only_needs_single_image_view",
                Provenance(file=str(split_dir)),
                suggestion="A split without metadata.jsonl inside a JSONL source imports only when the "
                "schema declares exactly one image view.",
            )
            return None
        return sorted(p for p in split_dir.rglob("*") if p.is_file() and classify_media(p) == "image")

    def _check_attrs(self, context: _LineContext, line: ParsedLine, report: PreflightReport) -> None:
        record_fields = set(context.info.record.model_fields) if context.info.record else set()
        for attr_name in line.model.attrs:
            if attr_name not in record_fields:
                report.add(
                    "unknown_record_attr",
                    line.provenance,
                    suggestion=f"Record attr '{attr_name}' is not declared in the schema.",
                )
        entity_fields = set(context.info.entity.model_fields) if context.info.entity else set()
        for entity in line.model.entities:
            for attr_name in entity.attrs:
                if attr_name not in entity_fields:
                    report.add(
                        "unknown_entity_attr",
                        line.provenance,
                        suggestion=f"Entity attr '{attr_name}' is not declared in the schema.",
                    )

    def _check_media(self, context: _LineContext, line: ParsedLine, report: PreflightReport) -> int:
        probed = 0
        for view_name, payload in line.views.items():
            kind = context.view_kinds[view_name]
            uri = getattr(payload, "uri", None)
            if (
                kind in ("image", "video", "point_cloud")
                and uri
                and not uri.startswith(("http://", "https://", "s3://"))
            ):
                candidate = context.split_dir / uri
                if not candidate.is_file():
                    report.add(
                        "missing_media",
                        Provenance(
                            file=str(line.provenance.file), line=line.line_number, json_pointer=f"/views/{view_name}"
                        ),
                        suggestion=f"File not found: {candidate}",
                    )
                probed += 1
            if kind == "sequence_frames" and payload.frame_pattern is not None:
                if payload.fps is None:
                    report.add(
                        "fps_required_for_pattern",
                        line.provenance,
                        suggestion="frame_pattern sequences need an explicit fps (nothing is inferred).",
                    )
                if not sorted(context.split_dir.glob(payload.frame_pattern)):
                    report.add(
                        "missing_media",
                        line.provenance,
                        suggestion=f"frame_pattern '{payload.frame_pattern}' matches no files.",
                    )
                probed += 1
        return probed

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def iter_batches(
        self,
        source: SourceRef,
        spec: ImportSpec,
        plan: ImportPlan,
        cursor: Cursor | None = None,
    ) -> Iterator[BatchBundle]:
        """Stream rows split by split, line by line, resuming past the cursor."""
        assert source.path is not None
        if is_media_only_source(source.path):
            yield from self._iter_media_only_source(source, spec, cursor)
            return
        info = self.resolve_info(spec, source)
        namespace = self.effective_namespace(spec, source)
        resume_split = cursor.get("split") if cursor else None
        resume_line = int(cursor.get("line", 0)) if cursor else 0

        for split_dir in _splits_of(source.path):
            if resume_split is not None:
                if split_dir.name < resume_split:
                    continue
            context = _LineContext(info, spec, split_dir, namespace)
            metadata_file = split_dir / METADATA_FILENAME

            if not metadata_file.is_file():
                yield from self._iter_media_only(context, split_dir, resume_split, resume_line)
                continue

            report = PreflightReport()  # ingest runs the same parser; errors raise below
            for line in parse_file(metadata_file, split_dir.name, context.view_kinds, report):
                if not report.is_valid:
                    first = next(iter(report.errors))
                    raise MetadataError(f"Invalid line during ingest: {first.code} — {first.suggestion}")
                if resume_split == split_dir.name and line.line_number <= resume_line:
                    continue
                tables = self._build_line(context, line)
                yield BatchBundle(
                    tables=tables,
                    cursor={"split": split_dir.name, "line": line.line_number},
                    provenance=line.provenance,
                )

    def _iter_media_only(
        self, context: _LineContext, split_dir: Path, resume_split: str | None, resume_line: int
    ) -> Iterator[BatchBundle]:
        media_files = self._media_only_files(context, PreflightReport(), split_dir)
        if media_files is None:
            raise SpecValidationError(
                f"Split '{split_dir.name}' has no {METADATA_FILENAME} and the schema does not declare "
                "exactly one image view."
            )
        view_name = context.single_view
        assert view_name is not None
        for ordinal, media_file in enumerate(media_files, start=1):
            if resume_split == split_dir.name and ordinal <= resume_line:
                continue
            record_id = stable_id(context.namespace, split_dir.name, media_file.stem, ordinal)
            record_cls = context.info.record
            assert record_cls is not None  # resolve_dataset_info always sets a record schema
            record = record_cls(id=record_id, split=split_dir.name)
            image_row = self._image_row(
                context, record_id, view_name, str(media_file.relative_to(split_dir)), None, None
            )
            yield BatchBundle(
                tables={"records": [record], "images": [image_row]},
                cursor={"split": split_dir.name, "line": ordinal},
            )

    def _iter_media_only_source(
        self, source: SourceRef, spec: ImportSpec, cursor: Cursor | None
    ) -> Iterator[BatchBundle]:
        """Ingest a bare media folder: one bundle per discovered record group."""
        assert source.path is not None
        info = self.resolve_info(spec, source)
        namespace = self.effective_namespace(spec, source)
        report = PreflightReport()
        folders = frames_mode(spec) == "folders"
        layout = discover_layout(source.path, view_kinds_of(info), report, folder_frames=folders)
        if not report.is_valid:
            first = next(iter(report.errors))
            raise SpecValidationError(f"Invalid media-only source: {first.code} — {first.suggestion}")
        max_frames = self._max_frames_per_video(spec)
        fps = folder_frames_fps(spec) if folders else 0.0
        resume_split = cursor.get("split") if cursor else None
        resume_line = int(cursor.get("line", 0)) if cursor else 0

        for split in layout.splits:
            if resume_split is not None and split.name < resume_split:
                continue
            context = _LineContext(info, spec, split.root, namespace)
            record_cls = info.record
            assert record_cls is not None  # resolve_dataset_info always sets a record schema
            for group in split.records:
                if resume_split == split.name and group.ordinal <= resume_line:
                    continue
                record_id = stable_id(namespace, split.name, group.key, group.ordinal)
                tables: dict[str, list[LanceModel]] = {"records": [record_cls(id=record_id, split=split.name)]}
                for view_name, media_file in sorted(group.files.items()):
                    relative = str(media_file.relative_to(split.root))
                    kind = context.view_kinds[view_name]
                    if kind == "image":
                        rows = [self._image_row(context, record_id, view_name, relative, None, None)]
                    elif kind == "text":
                        rows = [
                            self._text_row(context, record_id, view_name, SimpleNamespace(content=None, uri=relative))
                        ]
                    elif kind == "video":
                        payload = SimpleNamespace(uri=relative, fps=None, from_timestamp=0.0, to_timestamp=-1.0)
                        rows = [self._video_row(context, record_id, view_name, payload)]
                    elif kind == "sequence_frames":
                        if folders:
                            rows = self._media_only_folder_frames(
                                context, record_id, view_name, media_file, max_frames, fps
                            )
                        else:
                            rows = self._media_only_frames(context, record_id, view_name, media_file, max_frames)
                    else:  # pragma: no cover - discovery rejects unscannable kinds
                        raise SpecValidationError(f"View '{view_name}' kind '{kind}' has no media-only ingest.")
                    for row in rows:
                        tables.setdefault(canonical_table_name_for_schema(type(row)), []).append(row)
                yield BatchBundle(
                    tables=tables,
                    cursor={"split": split.name, "line": group.ordinal},
                    provenance=Provenance(file=str(split.root), record_key=group.key),
                )

    def _media_only_frames(
        self, context: _LineContext, record_id: str, view_name: str, video_file: Path, max_frames: int
    ) -> list[LanceModel]:
        """Extract a raw video's frames to SequenceFrame rows (uniform stride under the cap)."""
        probe = probe_video(video_file)
        fps = probe.fps
        if not fps:
            raise MetadataError(f"Could not determine the frame rate of '{video_file.name}'.")
        view_cls = context.info.views[view_name]
        rows: list[LanceModel] = []
        with tempfile.TemporaryDirectory(prefix="pixano-media-only-") as tmp:
            frame_files = decode_video_frames(video_file, tmp)
            if not frame_files:
                raise MediaResolutionError(f"'{video_file.name}' decoded to zero frames; re-encode it or remove it.")
            indices = list(range(len(frame_files)))
            if max_frames and len(indices) > max_frames:
                stride = len(indices) / max_frames
                indices = [int(position * stride) for position in range(max_frames)]
            for index in indices:
                rows.append(
                    view_cls(
                        id=stable_id(record_id, "view", view_name, index),
                        record_id=record_id,
                        logical_name=view_name,
                        uri="",
                        raw_bytes=frame_files[index].read_bytes(),
                        width=probe.width,
                        height=probe.height,
                        format="JPEG",
                        frame_index=index,
                        timestamp=index / fps,
                    )
                )
        return rows

    def _media_only_folder_frames(
        self,
        context: _LineContext,
        record_id: str,
        view_name: str,
        frames_dir: Path,
        max_frames: int,
        fps: float,
    ) -> list[LanceModel]:
        """Pre-extracted frames: one SequenceFrame per image, lexicographic name order (the invariant)."""
        view_cls = context.info.views[view_name]
        frame_files = frame_folder_files(frames_dir)
        indices = list(range(len(frame_files)))
        if max_frames and len(indices) > max_frames:
            stride = len(indices) / max_frames
            indices = [int(position * stride) for position in range(max_frames)]
        rows: list[LanceModel] = []
        for index in indices:
            frame = frame_files[index]
            relative = frame.relative_to(context.split_dir).as_posix()
            resolved = context.resolver.resolve(relative, None)
            width = height = 0
            image_format = frame.suffix.removeprefix(".").upper()
            if resolved.raw_bytes:
                width, height, image_format = probe_image(context.resolver.local_path(relative))
            rows.append(
                view_cls(
                    id=stable_id(record_id, "view", view_name, index),
                    record_id=record_id,
                    logical_name=view_name,
                    uri=resolved.uri,
                    raw_bytes=resolved.raw_bytes,
                    width=width,
                    height=height,
                    format=image_format,
                    frame_index=index,
                    timestamp=index / fps if fps else 0.0,
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Row construction
    # ------------------------------------------------------------------

    def _build_line(self, context: _LineContext, line: ParsedLine) -> dict[str, list[LanceModel]]:
        tables: dict[str, list[LanceModel]] = {}

        def add(table: str, row: LanceModel) -> None:
            tables.setdefault(table, []).append(row)

        record_id = line.model.id or stable_id(
            context.namespace, line.split, Path(str(line.provenance.file)).stem, line.line_number
        )
        record_cls = context.info.record
        if record_cls is None:
            raise MetadataError("The schema declares no record slot.", line.provenance)
        try:
            record = record_cls(id=record_id, split=line.split, **line.model.attrs)
        except ValidationError as exc:
            raise MetadataError(f"Record attrs do not match the schema: {exc}", line.provenance) from None
        add("records", record)

        view_rows: dict[str, LanceModel] = {}
        frame_rows: dict[str, dict[int, LanceModel]] = {}
        frame_stems: dict[str, dict[str, int]] = {}
        for view_name, payload in line.views.items():
            kind = context.view_kinds[view_name]
            if kind == "image":
                row = self._image_row(context, record_id, view_name, payload.uri, payload.width, payload.height)
                view_rows[view_name] = row
                add(canonical_table_name_for_schema(type(row)), row)
            elif kind == "video":
                row = self._video_row(context, record_id, view_name, payload)
                view_rows[view_name] = row
                add(canonical_table_name_for_schema(type(row)), row)
            elif kind == "sequence_frames":
                stem_rows = self._sequence_rows(context, record_id, view_name, payload)
                frame_rows[view_name] = {row.frame_index: row for _, row in stem_rows}
                frame_stems[view_name] = {stem: row.frame_index for stem, row in stem_rows}
                if stem_rows:
                    view_rows[view_name] = stem_rows[0][1]
                for _, row in stem_rows:
                    add(canonical_table_name_for_schema(type(row)), row)
            elif kind == "text":
                row = self._text_row(context, record_id, view_name, payload)
                view_rows[view_name] = row
                add(canonical_table_name_for_schema(type(row)), row)
            elif kind == "point_cloud":
                resolved = context.resolver.resolve(payload.uri, line.provenance)
                view_cls = context.info.views[view_name]
                row = view_cls(
                    id=stable_id(record_id, "view", view_name),
                    record_id=record_id,
                    logical_name=view_name,
                    uri=resolved.uri,
                    raw_bytes=resolved.raw_bytes,
                )
                view_rows[view_name] = row
                add(canonical_table_name_for_schema(type(row)), row)

        for ordinal, entity_spec in enumerate(line.model.entities):
            self._build_entity(context, line, record_id, ordinal, entity_spec, view_rows, frame_rows, add)

        for conv_ordinal, conversation in enumerate(line.model.conversations):
            self._build_conversation(context, line, record_id, conv_ordinal, conversation, view_rows, add)

        for sidecar in line.model.annotation_files:
            self._build_sidecar(context, line, record_id, sidecar, frame_rows, frame_stems, add)

        return tables

    def _image_row(
        self,
        context: _LineContext,
        record_id: str,
        view_name: str,
        uri: str,
        width: int | None,
        height: int | None,
    ) -> LanceModel:
        resolved = context.resolver.resolve(uri, None)
        image_format = Path(uri).suffix.removeprefix(".").upper() or "UNKNOWN"
        if resolved.raw_bytes and (width is None or height is None):
            local = context.resolver.local_path(uri)
            width, height, image_format = probe_image(local)
        view_cls = context.info.views[view_name]
        return view_cls(
            id=stable_id(record_id, "view", view_name),
            record_id=record_id,
            logical_name=view_name,
            uri=resolved.uri,
            raw_bytes=resolved.raw_bytes,
            width=width or 0,
            height=height or 0,
            format=image_format,
        )

    def _video_row(self, context: _LineContext, record_id: str, view_name: str, payload: Any) -> LanceModel:
        resolved = context.resolver.resolve(payload.uri, None)
        fps = payload.fps or 0.0
        width = height = 0
        num_frames = 0
        duration = 0.0
        video_format = Path(payload.uri).suffix.removeprefix(".")
        if resolved.raw_bytes:
            probe = probe_video(context.resolver.local_path(payload.uri))
            fps = payload.fps or probe.fps
            width, height = probe.width, probe.height
            duration = probe.duration if payload.to_timestamp < 0 else payload.to_timestamp - payload.from_timestamp
            num_frames = probe.num_frames if payload.to_timestamp < 0 else int(round(duration * fps))
            video_format = probe.format
        elif payload.to_timestamp >= 0 and fps:
            duration = payload.to_timestamp - payload.from_timestamp
            num_frames = int(round(duration * fps))
        view_cls = context.info.views[view_name]
        return view_cls(
            id=stable_id(record_id, "view", view_name),
            record_id=record_id,
            logical_name=view_name,
            uri=resolved.uri,
            raw_bytes=resolved.raw_bytes,
            fps=fps,
            width=width,
            height=height,
            num_frames=num_frames,
            duration=duration,
            format=video_format,
            from_timestamp=payload.from_timestamp,
            to_timestamp=payload.to_timestamp,
        )

    def _sequence_rows(
        self, context: _LineContext, record_id: str, view_name: str, payload: Any
    ) -> list[tuple[str, LanceModel]]:
        view_cls = context.info.views[view_name]
        if payload.frame_pattern is not None:
            if payload.fps is None:
                raise MetadataError("frame_pattern sequences need an explicit fps.")
            frame_files = sorted(context.split_dir.glob(payload.frame_pattern))
            frames = [
                (index, str(f.relative_to(context.split_dir)), index / payload.fps)
                for index, f in enumerate(frame_files)
            ]
        else:
            frames = []
            for position, frame in enumerate(payload.frames):
                index = frame.frame_index if frame.frame_index is not None else position
                timestamp = (
                    frame.timestamp if frame.timestamp is not None else (index / payload.fps if payload.fps else 0.0)
                )
                frames.append((index, frame.uri, timestamp))

        rows: list[tuple[str, LanceModel]] = []
        for index, uri, timestamp in frames:
            resolved = context.resolver.resolve(uri, None)
            width = height = 0
            image_format = Path(uri).suffix.removeprefix(".").upper()
            if resolved.raw_bytes:
                width, height, image_format = probe_image(context.resolver.local_path(uri))
            rows.append(
                (
                    Path(uri).stem,
                    view_cls(
                        id=stable_id(record_id, "view", view_name, index),
                        record_id=record_id,
                        logical_name=view_name,
                        uri=resolved.uri,
                        raw_bytes=resolved.raw_bytes,
                        width=width,
                        height=height,
                        format=image_format,
                        frame_index=index,
                        timestamp=timestamp,
                    ),
                )
            )
        return rows

    def _text_row(self, context: _LineContext, record_id: str, view_name: str, payload: Any) -> LanceModel:
        view_cls = context.info.views[view_name]
        if payload.content is not None:
            content, uri = payload.content, ""
        elif payload.uri.startswith(("http://", "https://", "s3://")):
            content, uri = "", payload.uri
        else:
            try:
                content, uri = context.resolver.local_path(payload.uri).read_text(encoding="utf-8"), ""
            except UnicodeDecodeError as error:
                raise MetadataError(f"Text file '{payload.uri}' is not valid UTF-8: {error}.") from None
        return view_cls(
            id=stable_id(record_id, "view", view_name),
            record_id=record_id,
            logical_name=view_name,
            uri=uri,
            content=content,
        )

    def _build_entity(
        self,
        context: _LineContext,
        line: ParsedLine,
        record_id: str,
        ordinal: int,
        entity_spec: EntitySpec,
        view_rows: dict[str, LanceModel],
        frame_rows: dict[str, dict[int, LanceModel]],
        add: Any,
    ) -> None:
        entity_cls = context.info.entity
        if entity_cls is None:
            raise MetadataError("The schema declares no entity slot but the line contains entities.", line.provenance)
        entity_id = entity_spec.id or stable_id(record_id, "ent", ordinal)
        try:
            entity = entity_cls(
                id=entity_id, record_id=record_id, parent_id=entity_spec.parent_id or "", **entity_spec.attrs
            )
        except ValidationError as exc:
            raise MetadataError(f"Entity attrs do not match the schema: {exc}", line.provenance) from None
        add("entities", entity)

        tracklet_ids: dict[str, str] = {}
        tracklet_cls = context.slot_schema("tracklet")
        if tracklet_cls is not None:
            tracklet_specs = list(entity_spec.tracklets)
            if not tracklet_specs:
                tracklet_specs = self._derive_tracklets(entity_spec, context)
            for tracklet_ordinal, tracklet_spec in enumerate(tracklet_specs):
                tracklet_id = tracklet_spec.id or stable_id(entity_id, "tracklet", tracklet_ordinal)
                tracklet_ids[tracklet_spec.view] = tracklet_id
                view_row = view_rows.get(tracklet_spec.view)
                fps = self._view_fps(line, tracklet_spec.view)
                add(
                    canonical_table_name_for_slot("tracklet"),
                    tracklet_cls(
                        id=tracklet_id,
                        record_id=record_id,
                        entity_id=entity_id,
                        view_id=view_row.id if view_row is not None else "",
                        start_timestep=tracklet_spec.start_timestep,
                        end_timestep=tracklet_spec.end_timestep,
                        start_timestamp=(
                            tracklet_spec.start_timestamp
                            if tracklet_spec.start_timestamp is not None
                            else (tracklet_spec.start_timestep / fps if fps else 0.0)
                        ),
                        end_timestamp=(
                            tracklet_spec.end_timestamp
                            if tracklet_spec.end_timestamp is not None
                            else (tracklet_spec.end_timestep / fps if fps else 0.0)
                        ),
                        source_type=line.defaults.source.type,
                        source_name=line.defaults.source.name,
                    ),
                )

        eds_cls = context.slot_schema("entity_dynamic_state")
        state_ids: dict[int, str] = {}
        if entity_spec.states and eds_cls is None:
            raise MetadataError("The schema declares no entity_dynamic_state slot but the line has states.")
        for state_ordinal, state in enumerate(entity_spec.states):
            assert eds_cls is not None  # guarded above
            state_view = entity_spec.tracklets[0].view if entity_spec.tracklets else (context.single_view or "")
            frame_row = frame_rows.get(state_view, {}).get(state.frame_index)
            view_row = view_rows.get(state_view)
            state_id = stable_id(entity_id, "state", state_ordinal)
            state_ids[state.frame_index] = state_id
            try:
                eds_row = eds_cls(
                    id=state_id,
                    record_id=record_id,
                    entity_id=entity_id,
                    tracklet_id=next(iter(tracklet_ids.values()), ""),
                    view_id=view_row.id if view_row is not None else "",
                    frame_id=frame_row.id if frame_row is not None else "",
                    frame_index=state.frame_index,
                    **state.attrs,
                )
            except ValidationError as exc:
                raise MetadataError(f"State attrs do not match the schema: {exc}", line.provenance) from None
            add(canonical_table_name_for_slot("entity_dynamic_state"), eds_row)

        for ann_ordinal, annotation in enumerate(entity_spec.annotations):
            view_name = annotation.view or context.single_view
            if view_name is None:
                raise MetadataError("Annotation without a view on a multi-view schema.", line.provenance)
            view_row = view_rows.get(view_name)
            frame_row = None
            if annotation.frame_index is not None:
                frame_row = frame_rows.get(view_name, {}).get(annotation.frame_index)
            source = annotation.source or line.defaults.source
            common = {
                "id": annotation.id or stable_id(entity_id, annotation.kind, ann_ordinal),
                "record_id": record_id,
                "entity_id": entity_id,
                "view_id": view_row.id if view_row is not None else "",
                "source_type": source.type,
                "source_name": source.name,
            }
            row = self._annotation_row(
                context, line, annotation, common, view_rows, frame_row, tracklet_ids, state_ids
            )
            if row is not None:
                add(canonical_table_name_for_schema(type(row)), row)

    def _annotation_row(
        self,
        context: _LineContext,
        line: ParsedLine,
        annotation: Any,
        common: dict[str, Any],
        view_rows: dict[str, LanceModel],
        frame_row: LanceModel | None,
        tracklet_ids: dict[str, str],
        state_ids: dict[int, str],
    ) -> LanceModel | None:
        per_frame = dict(common)
        if annotation.frame_index is not None:
            per_frame.update(
                frame_index=annotation.frame_index,
                frame_id=frame_row.id if frame_row is not None else "",
                tracklet_id=tracklet_ids.get(annotation.view or context.single_view or "", ""),
                entity_dynamic_state_id=state_ids.get(annotation.frame_index, ""),
            )

        if annotation.kind == "bbox":
            schema = context.slot_schema("bbox")
            if schema is None:
                raise MetadataError("bbox annotation but no bbox slot in the schema.", line.provenance)
            return schema(
                **per_frame,
                coords=annotation.coords,
                format=annotation.format or line.defaults.bbox.format,
                is_normalized=(
                    annotation.is_normalized
                    if annotation.is_normalized is not None
                    else bool(line.defaults.bbox.is_normalized)
                ),
                confidence=annotation.confidence,
            )
        if annotation.kind == "mask":
            schema = context.slot_schema("mask")
            if schema is None:
                raise MetadataError("mask annotation but no mask slot in the schema.", line.provenance)
            if annotation.rle is not None:
                return schema(**per_frame, size=annotation.rle.size, counts=annotation.rle.counts.encode("utf-8"))
            view_row = view_rows.get(annotation.view or context.single_view or "")
            height = getattr(view_row, "height", 0) if view_row is not None else 0
            width = getattr(view_row, "width", 0) if view_row is not None else 0
            if not height or not width:
                raise MetadataError(
                    "Polygon masks need the view's pixel dimensions (embed the image or set width/height).",
                    line.provenance,
                )
            polygons = [
                [coord * (width if index % 2 == 0 else height) for index, coord in enumerate(polygon)]
                for polygon in annotation.polygons
            ]
            from pixano.schemas import CompressedRLE

            rle = CompressedRLE.from_polygons(polygons, height=height, width=width)
            return schema(**per_frame, size=rle.size, counts=rle.counts)
        if annotation.kind == "keypoints":
            schema = context.slot_schema("keypoint")
            if schema is None:
                raise MetadataError("keypoints annotation but no keypoint slot in the schema.", line.provenance)
            return schema(
                **per_frame, template_id=annotation.template_id, coords=annotation.coords, states=annotation.states
            )
        if annotation.kind == "multi_path":
            schema = context.slot_schema("multi_path")
            if schema is None:
                raise MetadataError("multi_path annotation but no multi_path slot in the schema.", line.provenance)
            return schema(
                **per_frame, coords=annotation.coords, num_points=annotation.num_points, is_closed=annotation.is_closed
            )
        if annotation.kind == "text_span":
            schema = context.slot_schema("text_span")
            if schema is None:
                raise MetadataError("text_span annotation but no text_span slot in the schema.", line.provenance)
            return schema(
                **per_frame,
                mention=annotation.mention,
                spans_start=annotation.spans_start,
                spans_end=annotation.spans_end,
            )
        if annotation.kind == "classification":
            schema = context.slot_schema("classification")
            if schema is None:
                raise MetadataError(
                    "classification annotation but no classification slot in the schema.", line.provenance
                )
            return schema(
                **per_frame,
                labels=annotation.labels,
                confidences=annotation.confidences or [1.0] * len(annotation.labels),
            )
        return None

    def _derive_tracklets(self, entity_spec: EntitySpec, context: _LineContext) -> list[Any]:
        """Auto-derive one tracklet per view from per-frame annotations (spec §5)."""
        from .spec import TrackletSpec

        by_view: dict[str, list[int]] = {}
        for annotation in entity_spec.annotations:
            if annotation.frame_index is not None:
                view = annotation.view or context.single_view or ""
                by_view.setdefault(view, []).append(annotation.frame_index)
        return [
            TrackletSpec(view=view, start_timestep=min(indices), end_timestep=max(indices))
            for view, indices in sorted(by_view.items())
            if indices
        ]

    def _view_fps(self, line: ParsedLine, view_name: str) -> float:
        payload = line.views.get(view_name)
        return float(getattr(payload, "fps", 0.0) or 0.0)

    def _build_conversation(
        self,
        context: _LineContext,
        line: ParsedLine,
        record_id: str,
        conv_ordinal: int,
        conversation: Any,
        view_rows: dict[str, LanceModel],
        add: Any,
    ) -> None:
        message_cls = context.slot_schema("message")
        if message_cls is None:
            raise MetadataError("The schema declares no message slot but the line has conversations.", line.provenance)
        conversation_id = conversation.id or stable_id(record_id, "conv", conv_ordinal)
        question_number = -1
        for message_ordinal, message in enumerate(conversation.messages):
            if message.type == "QUESTION":
                question_number += 1
                number = question_number
            elif message.type == "ANSWER":
                number = max(question_number, 0)
            else:
                number = 0
            view_id = ""
            if message.views:
                view_row = view_rows.get(message.views[0])
                view_id = view_row.id if view_row is not None else ""
            add(
                canonical_table_name_for_slot("message"),
                message_cls(
                    id=stable_id(conversation_id, "msg", message_ordinal),
                    record_id=record_id,
                    conversation_id=conversation_id,
                    number=number,
                    user=message.user or line.defaults.source.name,
                    type=message.type,
                    content=message.content,
                    question_type=message.question_type or "",
                    choices=message.choices or [],
                    view_id=view_id,
                    source_type=line.defaults.source.type,
                    source_name=line.defaults.source.name,
                ),
            )

    def _build_sidecar(
        self,
        context: _LineContext,
        line: ParsedLine,
        record_id: str,
        sidecar: SidecarSpec,
        frame_rows: dict[str, dict[int, LanceModel]],
        frame_stems: dict[str, dict[str, int]],
        add: Any,
    ) -> None:
        view_frames = frame_rows.get(sidecar.view, {})
        frames_by_stem = {
            stem: (index, view_frames[index]) for stem, index in frame_stems.get(sidecar.view, {}).items()
        }
        if not frames_by_stem:
            raise MetadataError(
                f"annotation_files sidecars need a sequence_frames view ('{sidecar.view}').", line.provenance
            )
        sidecar_files = sorted(context.split_dir.glob(sidecar.pattern))
        if sidecar.encoding == "index_png":
            self._build_mask_sidecar(context, line, record_id, sidecar, sidecar_files, frames_by_stem, add)
        else:
            self._build_track_sidecar(context, line, record_id, sidecar, sidecar_files, frames_by_stem, add)

    def _build_mask_sidecar(self, context, line, record_id, sidecar, sidecar_files, frames_by_stem, add) -> None:
        from pixano.schemas import CompressedRLE

        mask_cls = context.slot_schema("mask")
        entity_cls = context.info.entity
        if mask_cls is None or entity_cls is None:
            raise MetadataError("index_png sidecars need mask and entity slots in the schema.", line.provenance)
        entity_map = sidecar.entity_map
        entities: dict[str, LanceModel] = {}
        appearances: dict[str, list[int]] = {}

        for sidecar_file in sidecar_files:
            frame_info = frames_by_stem.get(sidecar_file.stem)
            if frame_info is None:
                continue
            frame_index, frame_row = frame_info
            for entity_key, binary_mask in decode_index_png(sidecar_file, entity_map).items():
                if not binary_mask.any():
                    continue
                if entity_key not in entities:
                    entity_id = stable_id(record_id, "ent", entity_key)
                    entities[entity_key] = entity_cls(id=entity_id, record_id=record_id)
                    add("entities", entities[entity_key])
                    appearances[entity_key] = []
                appearances[entity_key].append(frame_index)
                rle = CompressedRLE.from_mask(binary_mask)
                add(
                    canonical_table_name_for_slot("mask"),
                    mask_cls(
                        id=stable_id(entities[entity_key].id, "mask", frame_index),
                        record_id=record_id,
                        entity_id=entities[entity_key].id,
                        view_id=frame_row.id,
                        frame_id=frame_row.id,
                        frame_index=frame_index,
                        size=rle.size,
                        counts=rle.counts,
                        source_type=line.defaults.source.type,
                        source_name=line.defaults.source.name,
                    ),
                )

        tracklet_cls = context.slot_schema("tracklet")
        if tracklet_cls is not None:
            fps = self._view_fps(line, sidecar.view)
            for entity_key, frames in appearances.items():
                add(
                    canonical_table_name_for_slot("tracklet"),
                    tracklet_cls(
                        id=stable_id(entities[entity_key].id, "tracklet", 0),
                        record_id=record_id,
                        entity_id=entities[entity_key].id,
                        start_timestep=min(frames),
                        end_timestep=max(frames),
                        start_timestamp=min(frames) / fps if fps else 0.0,
                        end_timestamp=max(frames) / fps if fps else 0.0,
                        source_type=line.defaults.source.type,
                        source_name=line.defaults.source.name,
                    ),
                )

    def _build_track_sidecar(self, context, line, record_id, sidecar, sidecar_files, frames_by_stem, add) -> None:
        bbox_cls = context.slot_schema("bbox")
        entity_cls = context.info.entity
        if bbox_cls is None or entity_cls is None:
            raise MetadataError("track_json sidecars need bbox and entity slots in the schema.", line.provenance)
        if line.defaults.bbox.format is None or line.defaults.bbox.is_normalized is None:
            raise MetadataError(
                "track_json sidecars need bbox defaults (format, is_normalized) in the header.", line.provenance
            )
        entities: dict[int, LanceModel] = {}
        appearances: dict[int, list[int]] = {}

        for sidecar_file in sidecar_files:
            frame_info = frames_by_stem.get(sidecar_file.stem)
            if frame_info is None:
                continue
            frame_index, frame_row = frame_info
            for track_object in decode_track_json(sidecar_file).objects:
                if track_object.track_id not in entities:
                    entity_id = stable_id(record_id, "ent", "track", track_object.track_id)
                    attrs = {"category": track_object.category} if "category" in entity_cls.model_fields else {}
                    entities[track_object.track_id] = entity_cls(id=entity_id, record_id=record_id, **attrs)
                    add("entities", entities[track_object.track_id])
                    appearances[track_object.track_id] = []
                appearances[track_object.track_id].append(frame_index)
                add(
                    canonical_table_name_for_slot("bbox"),
                    bbox_cls(
                        id=stable_id(entities[track_object.track_id].id, "bbox", frame_index),
                        record_id=record_id,
                        entity_id=entities[track_object.track_id].id,
                        view_id=frame_row.id,
                        frame_id=frame_row.id,
                        frame_index=frame_index,
                        coords=track_object.bbox,
                        format=line.defaults.bbox.format,
                        is_normalized=line.defaults.bbox.is_normalized,
                        confidence=1.0,
                        source_type=line.defaults.source.type,
                        source_name=line.defaults.source.name,
                    ),
                )

        tracklet_cls = context.slot_schema("tracklet")
        if tracklet_cls is not None:
            fps = self._view_fps(line, sidecar.view)
            for track_id, frames in appearances.items():
                add(
                    canonical_table_name_for_slot("tracklet"),
                    tracklet_cls(
                        id=stable_id(entities[track_id].id, "tracklet", 0),
                        record_id=record_id,
                        entity_id=entities[track_id].id,
                        start_timestep=min(frames),
                        end_timestep=max(frames),
                        start_timestamp=min(frames) / fps if fps else 0.0,
                        end_timestamp=max(frames) / fps if fps else 0.0,
                        source_type=line.defaults.source.type,
                        source_name=line.defaults.source.name,
                    ),
                )


def _detect(source: SourceRef) -> DetectResult | None:
    return PixanoJsonlImporter().probe(source)


PIXANO_JSONL = DataFormat(
    name="pixano_jsonl",
    title="Pixano JSONL v2",
    importer_cls=PixanoJsonlImporter,
    capabilities=Capabilities(
        media_kinds=frozenset({"image", "video", "sequence_frames", "text", "point_cloud"}),
        annotation_kinds=frozenset(
            {"bbox", "mask", "keypoints", "multi_path", "text_span", "classification", "message"}
        ),
        source_kinds=frozenset({"local_dir"}),
        supports_resume=True,
        deterministic_ids=True,
    ),
    detect=_detect,
)
