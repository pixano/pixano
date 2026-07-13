# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Media-only sources: folders of raw images / videos / text without metadata (spec §7.1).

A media-only source has no ``dataset.yaml`` and no ``metadata.jsonl`` anywhere;
every media file becomes one record (grouped across view folders by stem).
Discovery is a single deterministic function shared by analyze, resolve_info,
and ingest, so the schema the user confirms at plan time is exactly what
ingest builds.
"""

from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pixano.utils import to_snake_case

from ...errors import MediaResolutionError, SpecValidationError
from ...media import VIDEO_EXTENSIONS
from ...plan import PreflightReport, Provenance
from ...spec import ImportSpec


_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"})
_TEXT_SUFFIXES = frozenset({".txt", ".md"})
_VIDEO_SUFFIXES = frozenset(VIDEO_EXTENSIONS)

# File kind -> accepted suffixes. Declared view kinds map onto file kinds below.
_KIND_SUFFIXES: dict[str, frozenset[str]] = {
    "image": _IMAGE_SUFFIXES,
    "video": _VIDEO_SUFFIXES,
    "text": _TEXT_SUFFIXES,
}

# View kind (schema dialect) -> file kind scanned on disk. A sequence_frames
# view in a media-only source consumes video files (frames extract at ingest).
_FILE_KIND_OF_VIEW_KIND: dict[str, str] = {
    "image": "image",
    "video": "video",
    "sequence_frames": "video",
    "text": "text",
}

_SPLIT_DIR_NAMES = frozenset({"train", "training", "val", "valid", "validation", "test", "testing"})

METADATA_FILENAME = "metadata.jsonl"


@dataclass
class RecordGroup:
    """One record: media files keyed by logical view name."""

    key: str
    ordinal: int
    files: dict[str, Path] = field(default_factory=dict)


@dataclass
class SplitLayout:
    """One split's discovered records, sorted and 1-ordinal'd for stable ids."""

    name: str
    root: Path
    records: list[RecordGroup] = field(default_factory=list)


@dataclass
class MediaLayout:
    """The discovered source layout: file kind per view, records per split."""

    view_kinds: dict[str, str] = field(default_factory=dict)  # logical view name -> file kind
    splits: list[SplitLayout] = field(default_factory=list)
    media_bytes: int = 0

    @property
    def total_records(self) -> int:
        """Total record count across splits."""
        return sum(len(split.records) for split in self.splits)


def classify_media(path: Path) -> str | None:
    """Return the file kind (image/video/text) of a path, or None."""
    suffix = path.suffix.lower()
    for kind, suffixes in _KIND_SUFFIXES.items():
        if suffix in suffixes:
            return kind
    return None


def frames_mode(spec: ImportSpec) -> str:
    """The raw-video handling mode: extract frames (default) or reference clips."""
    mode = str(spec.options.get("frames", "extract"))
    if mode not in ("extract", "reference"):
        raise SpecValidationError(f"Invalid frames mode '{mode}' (extract or reference).")
    return mode


def is_media_only_source(source_dir: Path) -> bool:
    """True when the folder holds bare media files and no split metadata.jsonl.

    A ``dataset.yaml`` does not disqualify a source: the spec merges before
    analyze, and a spec next to bare media folders is still a media-only import.
    """
    if not source_dir.is_dir() or (source_dir / METADATA_FILENAME).is_file():
        return False
    for subdir in _subdirs(source_dir):
        if (subdir / METADATA_FILENAME).is_file():
            return False
    return any(classify_media(p) is not None for p in source_dir.rglob("*") if p.is_file())


def discover_layout(source_dir: Path, declared_views: dict[str, str] | None, report: PreflightReport) -> MediaLayout:
    """Discover a media-only source's splits, views, and record groups.

    ``declared_views`` maps logical view names to schema view kinds when the
    spec declares them; ``None`` infers views from the folder layout. Layout
    problems land in ``report`` as findings; the returned layout holds
    whatever was unambiguously discovered.
    """
    layout = MediaLayout()
    if declared_views:
        unsupported = {v: k for v, k in declared_views.items() if k not in _FILE_KIND_OF_VIEW_KIND}
        if unsupported:
            report.add(
                "unsupported_view_kind_for_media_only",
                Provenance(file=str(source_dir)),
                suggestion=f"View kind(s) {sorted(set(unsupported.values()))} cannot be scanned from a media "
                "folder; provide a metadata.jsonl source instead.",
            )
            return layout
        layout.view_kinds = {name: _FILE_KIND_OF_VIEW_KIND[kind] for name, kind in declared_views.items()}
        layout.splits = _declared_layout(source_dir, layout.view_kinds, report)
    else:
        _infer_layout(source_dir, layout, report)

    if not report.errors and layout.total_records == 0:
        report.add(
            "no_media_found",
            Provenance(file=str(source_dir)),
            suggestion="No importable media files were found under the source folder.",
        )
    layout.media_bytes = sum(
        f.stat().st_size for split in layout.splits for group in split.records for f in group.files.values()
    )
    return layout


# ---------------------------------------------------------------------------
# Declared-views discovery
# ---------------------------------------------------------------------------


def _declared_layout(source_dir: Path, view_kinds: dict[str, str], report: PreflightReport) -> list[SplitLayout]:
    reserved = sorted(name for name in view_kinds if name.lower() in _SPLIT_DIR_NAMES)
    if reserved:
        report.add(
            "view_name_reserved",
            Provenance(file=str(source_dir)),
            suggestion=f"View name(s) {reserved} collide with split folder names "
            f"({', '.join(sorted(_SPLIT_DIR_NAMES))}); rename the view(s).",
        )
        return []

    subdirs = _subdirs(source_dir)
    split_named = bool(subdirs) and all(d.name.lower() in _SPLIT_DIR_NAMES for d in subdirs)

    if len(view_kinds) >= 2:
        matched = _match_view_dirs(source_dir, view_kinds, report)
        if matched is None:
            return []
        if matched and not split_named:
            # View folders at the root (missing ones surface per-view findings).
            return [_view_dir_split("default", source_dir, matched, view_kinds, report)]
        if split_named:
            splits = []
            for subdir in subdirs:
                split_matched = _match_view_dirs(subdir, view_kinds, report)
                if split_matched is None:
                    return []
                splits.append(_view_dir_split(subdir.name, subdir, split_matched, view_kinds, report))
            return splits
        report.add(
            "view_folder_missing",
            Provenance(file=str(source_dir)),
            suggestion="Each declared view needs a folder <source>/<view>/ or <source>/<split>/<view>/; "
            f"declared views: {sorted(view_kinds)}.",
        )
        return []

    # Single declared view.
    (view_name, file_kind) = next(iter(view_kinds.items()))
    if split_named:
        _warn_root_files(source_dir, report)
        return [_flat_split(d.name, d, view_name, file_kind, report) for d in subdirs]
    matched = _match_view_dirs(source_dir, view_kinds, report)
    if matched is None:
        return []
    if view_name in matched:
        # <source>/<view>/ at the root: one 'default' split (mirrors inference).
        per_view = {view_name: _keyed_files(matched[view_name], file_kind, report)}
        return [SplitLayout(name="default", root=source_dir, records=_group_by_key(per_view, report))]
    if subdirs:
        # Legacy layout: every subdir is a split, scanned recursively.
        _warn_root_files(source_dir, report)
        for subdir in subdirs:
            if subdir.name.lower() not in _SPLIT_DIR_NAMES:
                report.add(
                    "subdirs_treated_as_splits",
                    Provenance(file=str(subdir)),
                    severity="warning",
                    suggestion=f"Folder '{subdir.name}' becomes a split because the schema declares the single "
                    f"view '{view_name}' and no folder matches it; use split names (train/val/test) or a "
                    f"'{view_name}/' folder if this is not intended.",
                )
        return [_flat_split(d.name, d, view_name, file_kind, report) for d in subdirs]
    return [_flat_split("default", source_dir, view_name, file_kind, report)]


def _match_view_dirs(root: Path, view_kinds: dict[str, str], report: PreflightReport) -> dict[str, Path] | None:
    """Resolve declared view names to subfolders (exact or snake_cased folder names).

    A declared name claimed by more than one folder (e.g. ``Left Cam/`` and
    ``left_cam/`` both snake-casing to ``left_cam``) is reported as an error
    and returns ``None`` — never a silent first-match pick.
    """
    claims: dict[str, list[Path]] = {}
    for subdir in _subdirs(root):
        for name in {subdir.name, to_snake_case(subdir.name)}:
            claims.setdefault(name, []).append(subdir)
    matched: dict[str, Path] = {}
    collided = False
    for name in view_kinds:
        candidates = claims.get(name, [])
        if len(candidates) > 1:
            folders = ", ".join(f"'{d.name}'" for d in sorted(candidates))
            report.add(
                "view_name_collision",
                Provenance(file=str(root)),
                suggestion=f"Folders {folders} all match declared view '{name}'; rename or remove the extras.",
            )
            collided = True
            continue
        if candidates:
            matched[name] = candidates[0]
    return None if collided else matched


def _view_dir_split(
    split_name: str,
    split_root: Path,
    matched: dict[str, Path],
    view_kinds: dict[str, str],
    report: PreflightReport,
) -> SplitLayout:
    per_view: dict[str, dict[str, Path]] = {}
    for view_name, file_kind in sorted(view_kinds.items()):
        view_dir = matched.get(view_name)
        if view_dir is None:
            report.add(
                "view_folder_missing",
                Provenance(file=str(split_root / view_name)),
                suggestion=f"Declared view '{view_name}' has no folder under '{split_root}'.",
            )
            continue
        per_view[view_name] = _keyed_files(view_dir, file_kind, report)
    return SplitLayout(name=split_name, root=split_root, records=_group_by_key(per_view, report))


def _flat_split(
    split_name: str, split_root: Path, view_name: str, file_kind: str, report: PreflightReport
) -> SplitLayout:
    """A recursively scanned single-view split, keyed by stem (the legacy grouping)."""
    files = _scan_files(split_root, file_kind)
    _report_duplicate_stems(files, split_root, report)
    records = [
        RecordGroup(key=f.stem, ordinal=ordinal, files={view_name: f}) for ordinal, f in enumerate(files, start=1)
    ]
    return SplitLayout(name=split_name, root=split_root, records=records)


# ---------------------------------------------------------------------------
# Inference (no declared views)
# ---------------------------------------------------------------------------


def _infer_layout(source_dir: Path, layout: MediaLayout, report: PreflightReport) -> None:
    subdirs = _subdirs(source_dir)
    media_subdirs = [d for d in subdirs if _has_media(d)]
    split_like = [d for d in media_subdirs if d.name.lower() in _SPLIT_DIR_NAMES]
    if split_like and len(split_like) != len(media_subdirs):
        report.add(
            "ambiguous_media_layout",
            Provenance(file=str(source_dir)),
            suggestion="Folders mix split names (train/val/test) with other media folders; "
            "reorganize the source or declare schema.views.",
        )
        return

    split_roots = {d.name: d for d in split_like} if split_like else {"default": source_dir}
    if split_like:
        _warn_root_files(source_dir, report)

    for split_name, split_root in sorted(split_roots.items()):
        view_files = _infer_split_views(split_root, report, is_source_root=split_root == source_dir)
        if view_files is None:
            return
        view_kinds = {name: kind for name, (kind, _) in view_files.items()}
        if layout.splits and view_kinds != layout.view_kinds:
            report.add(
                "inconsistent_split_views",
                Provenance(file=str(split_root)),
                suggestion=f"Split '{split_name}' implies views {sorted(view_kinds)} but "
                f"'{layout.splits[0].name}' implied {sorted(layout.view_kinds)}; make splits uniform "
                "or declare schema.views.",
            )
            return
        layout.view_kinds = view_kinds
        per_view = {name: keyed for name, (_, keyed) in view_files.items()}
        layout.splits.append(SplitLayout(name=split_name, root=split_root, records=_group_by_key(per_view, report)))


def _infer_split_views(
    split_root: Path, report: PreflightReport, is_source_root: bool
) -> dict[str, tuple[str, dict[str, Path]]] | None:
    """Infer one split's views: {logical_name: (file_kind, {key: file})} or None on ambiguity."""
    subdirs = _subdirs(split_root)
    if is_source_root:
        subdirs = [d for d in subdirs if d.name.lower() not in _SPLIT_DIR_NAMES]
    view_dirs = [d for d in subdirs if _has_media(d)]
    direct = sorted(p for p in split_root.iterdir() if p.is_file() and classify_media(p) is not None)

    if view_dirs and direct:
        report.add(
            "ambiguous_media_layout",
            Provenance(file=str(split_root)),
            suggestion="Media files sit both directly in the folder and inside subfolders; "
            "move them into view folders or declare schema.views.",
        )
        return None

    if not view_dirs:
        if not direct:
            return {}  # nothing importable here; the caller reports no_media_found
        kind = _sole_kind(direct, split_root, report)
        if kind is None:
            return None
        keyed = {f.stem: f for f in direct}
        if len(keyed) != len(direct):
            _report_duplicate_stems(direct, split_root, report)
            return None
        return {kind: (kind, keyed)}

    views: dict[str, tuple[str, dict[str, Path]]] = {}
    named_dirs: dict[str, Path] = {}
    for view_dir in sorted(view_dirs):
        files = sorted(p for p in view_dir.rglob("*") if p.is_file() and classify_media(p) is not None)
        kind = _sole_kind(files, view_dir, report)
        if kind is None:
            return None
        name = to_snake_case(view_dir.name)
        if name in views:
            report.add(
                "view_name_collision",
                Provenance(file=str(view_dir)),
                suggestion=f"Folders '{named_dirs[name].name}' and '{view_dir.name}' both map to view "
                f"'{name}'; rename one.",
            )
            return None
        keyed = _keyed_files(view_dir, kind, report)
        views[name] = (kind, keyed)
        named_dirs[name] = view_dir
    return views


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _subdirs(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.is_dir() and not p.name.startswith("."))


def _has_media(directory: Path) -> bool:
    return any(classify_media(p) is not None for p in directory.rglob("*") if p.is_file())


def _scan_files(root: Path, file_kind: str) -> list[Path]:
    suffixes = _KIND_SUFFIXES[file_kind]
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)


def _keyed_files(view_dir: Path, file_kind: str, report: PreflightReport) -> dict[str, Path]:
    """View files keyed by their relative path without suffix (the stem-match key)."""
    keyed: dict[str, Path] = {}
    for f in _scan_files(view_dir, file_kind):
        key = f.relative_to(view_dir).with_suffix("").as_posix()
        if key in keyed:
            report.add(
                "duplicate_view_stem",
                Provenance(file=str(f)),
                suggestion=f"'{key}' appears more than once under '{view_dir.name}/'; "
                "stems must be unique per view.",
            )
            continue
        keyed[key] = f
    return keyed


def _group_by_key(per_view: dict[str, dict[str, Path]], report: PreflightReport) -> list[RecordGroup]:
    """Stem-match files across views: one record per key, missing views warned."""
    if len(per_view) == 1:
        (view_name, keyed) = next(iter(per_view.items()))
        return [
            RecordGroup(key=key, ordinal=ordinal, files={view_name: keyed[key]})
            for ordinal, key in enumerate(sorted(keyed), start=1)
        ]
    all_keys = sorted({key for keyed in per_view.values() for key in keyed})
    records = []
    for ordinal, key in enumerate(all_keys, start=1):
        files = {view_name: keyed[key] for view_name, keyed in per_view.items() if key in keyed}
        for view_name in per_view:
            if view_name not in files:
                report.add(
                    "missing_view_file",
                    Provenance(file=f"{view_name}/{key}"),
                    severity="warning",
                    suggestion=f"Record '{key}' has no file under view '{view_name}'; the view is omitted "
                    "for that record.",
                )
        records.append(RecordGroup(key=key, ordinal=ordinal, files=files))
    return records


def _sole_kind(files: list[Path], where: Path, report: PreflightReport) -> str | None:
    kinds = sorted({kind for f in files if (kind := classify_media(f)) is not None})
    if len(kinds) != 1:
        report.add(
            "mixed_media_kinds",
            Provenance(file=str(where)),
            suggestion=f"'{where.name}' mixes {', '.join(kinds) or 'no'} media files; keep one kind per "
            "folder or declare schema.views.",
        )
        return None
    return kinds[0]


def _report_duplicate_stems(files: list[Path], where: Path, report: PreflightReport) -> None:
    seen: set[str] = set()
    for f in files:
        if f.stem in seen:
            report.add(
                "duplicate_view_stem",
                Provenance(file=str(f)),
                suggestion=f"'{f.stem}' appears with several extensions under '{where.name}'; "
                "stems must be unique.",
            )
        seen.add(f.stem)


def _warn_root_files(source_dir: Path, report: PreflightReport) -> None:
    for f in sorted(source_dir.iterdir()):
        if f.is_file() and classify_media(f) is not None:
            report.add(
                "files_outside_splits",
                Provenance(file=str(f)),
                severity="warning",
                suggestion="Media files at the source root are ignored when the source has split folders.",
            )


# ---------------------------------------------------------------------------
# Media helpers for analyze/ingest
# ---------------------------------------------------------------------------


def decode_video_frames(video: Path, tmp_dir: str) -> list[Path]:
    """Decode every encoded frame of a video to JPEG files (LeRobot's passthrough recipe)."""
    command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(video)]
    command += ["-fps_mode", "passthrough", "-q:v", "2", f"{tmp_dir}/%06d.jpg"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 and "fps_mode" in (result.stderr or ""):
        command[command.index("-fps_mode")] = "-vsync"  # pre-5.1 ffmpeg
        result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise MediaResolutionError(f"ffmpeg frame extraction failed on '{video.name}': {result.stderr.strip()[:200]}")
    return sorted(Path(tmp_dir).glob("*.jpg"))


def thumbnail_data_url(path: Path, size: int = 64) -> str | None:
    """A small data-URL JPEG thumbnail of an image file (plan previews); None on failure."""
    try:
        import PIL.Image

        with PIL.Image.open(path) as image:
            image.thumbnail((size, size))
            buffer = BytesIO()
            image.convert("RGB").save(buffer, format="JPEG")
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None
