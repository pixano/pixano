# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The LeRobot importer: episodes become annotatable frame sequences (spec §7.3).

Default mode extracts each episode's camera footage to `SequenceFrame` rows
(the DAVIS pattern) because the 0.8 UI displays and annotates frame
sequences. Scale guards: `max_frames_per_episode` uniform stride and the
plan's size estimate. The opt-in `frames: "reference"` mode emits `Video`
time-window rows instead (browse-scale, no annotation UI in 0.8).

Options (ImportSpec.options): `episodes` (list or "start:end"), `frames`
("extract" | "reference"), `max_frames_per_episode` (int).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

from lancedb.pydantic import LanceModel

from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import canonical_table_name_for_schema

from ...errors import MetadataError
from ...ids import stable_id
from ...importer import BatchBundle, Cursor, DatasetImporter, DetectResult, SourceRef
from ...media import MediaResolver, ffmpeg_available, ffprobe_available, probe_video
from ...plan import AnalyzeLimits, ImportPlan, Provenance, SamplePreview
from ...registry import Capabilities, DataFormat
from ...spec import ImportSpec, resolve_dataset_info
from .hub import materialize_files, materialize_meta
from .layout import Episode, LeRobotLayout, camera_view_name, parse_episode_selection, parse_layout


_JPEG_BYTES_PER_PIXEL = 0.12  # rough JPEG size estimate for the analyze plan


class LeRobotImporter(DatasetImporter):
    """Importer for LeRobot v2.1 and v3 datasets (local directories)."""

    format_name = "lerobot"
    importer_version = "1.0.0"
    supports_resume = True
    deterministic_ids = True

    # ------------------------------------------------------------------
    # Detection & schema
    # ------------------------------------------------------------------

    def _local_root(self, source: SourceRef) -> Path:
        """The layout root: the local path, or the hub snapshot (meta downloaded)."""
        if source.path is not None:
            return source.path
        if source.kind == "hf_hub" and source.url:
            return materialize_meta(source.url)
        raise MetadataError(f"Unsupported LeRobot source: {source.location()}")

    def probe(self, source: SourceRef) -> DetectResult | None:
        """Sniff for meta/info.json carrying a LeRobot codebase_version."""
        if source.kind == "hf_hub":
            # The only hub-capable format today; analyze materializes meta/ and
            # fails loud there if the repo is not a LeRobot dataset.
            return DetectResult(confidence=0.6, evidence="Hugging Face hub dataset id")
        if source.path is None or not (source.path / "meta" / "info.json").is_file():
            return None
        content = (source.path / "meta" / "info.json").read_text(encoding="utf-8")
        if "codebase_version" in content and "fps" in content:
            return DetectResult(confidence=0.95, evidence="meta/info.json with codebase_version")
        return None

    def resolve_info(self, spec: ImportSpec, source: SourceRef | None = None) -> DatasetInfo:
        """LeRobot's schema depends on the source's cameras; a user schema still wins."""
        if spec.schema_ is not None or spec.schema_manifest is not None or source is None:
            return resolve_dataset_info(spec)
        layout = parse_layout(self._local_root(source))
        view_kind = "sequence_frames" if self._frames_mode(spec) == "extract" else "video"
        payload = spec.model_dump(mode="json", exclude_none=True, by_alias=True)
        if payload.get("dataset", {}).get("workspace", "undefined") == "undefined":
            # Formats know their natural UI workspace; an explicit --workspace wins.
            payload.setdefault("dataset", {})["workspace"] = "video"
        payload["schema"] = {
            "views": {camera_view_name(key): {"kind": view_kind} for key in layout.video_keys},
            "record": {
                "attrs": {
                    "episode_index": "int",
                    "tasks": {"type": "str", "collection": True},
                    "length": "int",
                }
            },
            "annotations": ["bbox", "mask", "tracklet"],
        }
        info = resolve_dataset_info(ImportSpec.model_validate(payload))
        if layout.feature_dims and self._frames_mode(spec) == "extract":
            # State/action vectors ride a timeseries table (fixed-size Vector
            # columns are outside the YAML dialect, so attach programmatically).
            from pixano.schemas import create_timeseries_schema
            from pixano.utils import to_snake_case

            vector_fields = {to_snake_case(key.replace(".", "_")): dim for key, dim in layout.feature_dims.items()}
            slots = {
                slot: getattr(info, slot)
                for slot in (
                    "record",
                    "entity",
                    "entity_dynamic_state",
                    "bbox",
                    "mask",
                    "multi_path",
                    "keypoint",
                    "classification",
                    "relation",
                    "tracklet",
                    "message",
                    "text_span",
                )
                if getattr(info, slot, None) is not None
            }
            info = DatasetInfo(
                name=info.name,
                description=info.description,
                workspace=info.workspace,
                views=info.views,
                timeseries=create_timeseries_schema(vector_fields),
                **slots,
            )
        return info

    @staticmethod
    def _frames_mode(spec: ImportSpec) -> str:
        mode = str(spec.options.get("frames", "extract"))
        if mode not in ("extract", "reference"):
            raise MetadataError(f"Invalid frames mode '{mode}' (extract or reference).")
        return mode

    # ------------------------------------------------------------------
    # Analyze
    # ------------------------------------------------------------------

    def analyze(self, source: SourceRef, spec: ImportSpec, limits: AnalyzeLimits) -> ImportPlan:
        """Parse the layout, validate tooling and codecs, and estimate the extract size."""
        plan = ImportPlan(format=self.format_name, importer_version=self.importer_version)
        try:
            root = self._local_root(source)
        except MetadataError as error:
            plan.report.add("invalid_source", Provenance(file=source.location()), suggestion=str(error))
            return plan
        if not root.is_dir():
            plan.report.add("invalid_source", Provenance(file=source.location()), suggestion="Expected a directory.")
            return plan
        try:
            layout = parse_layout(root)
        except MetadataError as error:
            plan.report.add("invalid_layout", Provenance(file=str(root)), suggestion=str(error))
            return plan
        is_hub = source.kind == "hf_hub"

        episodes = self._select_episodes(layout, spec)
        mode = self._frames_mode(spec)
        provenance = Provenance(file=str(root / "meta" / "info.json"))

        if mode == "extract" and not (ffmpeg_available() and ffprobe_available()):
            plan.report.add(
                "ffmpeg_required",
                provenance,
                suggestion="Frame extraction needs ffmpeg+ffprobe on PATH; install ffmpeg or use "
                'options {"frames": "reference"}.',
            )

        # Probe one shard per camera: codec finding + size estimate.
        total_frames = 0
        for key in layout.video_keys:
            first = next((episode.cameras[key] for episode in episodes if key in episode.cameras), None)
            if first is None:
                continue
            shard = root / first.video_path
            if not shard.is_file():
                if is_hub:
                    continue  # shards download at ingest; meta-only analyze stays fast
                plan.report.add(
                    "missing_media",
                    Provenance(file=str(shard)),
                    suggestion=f"Video shard for camera '{key}' not found.",
                )
                continue
            if ffprobe_available():
                probe = probe_video(shard)
                if probe.codec == "av1":
                    plan.report.add(
                        "av1_codec",
                        Provenance(file=str(shard)),
                        severity="warning",
                        suggestion="AV1 shards decode for frame extraction but do not play in Safari; "
                        "documented limitation.",
                    )
                if mode == "extract":
                    cap = self._max_frames(spec)
                    for episode in episodes:
                        camera = episode.cameras.get(key)
                        if camera is None:
                            continue
                        duration = (
                            camera.to_timestamp - camera.from_timestamp if camera.to_timestamp > 0 else probe.duration
                        )
                        episode_frames = int(duration * layout.fps) if layout.fps else probe.num_frames
                        total_frames += min(episode_frames, cap) if cap else episode_frames
                    plan.totals.media_bytes = int(
                        (plan.totals.media_bytes or 0)
                        + total_frames * probe.width * probe.height * _JPEG_BYTES_PER_PIXEL
                    )

        for episode in episodes[: limits.max_previews]:
            plan.previews.append(
                SamplePreview(
                    record={"episode_index": episode.index, "tasks": episode.tasks, "length": episode.length}
                )
            )
        plan.splits["train"] = len(episodes)
        plan.totals.records = len(episodes)
        return plan

    @staticmethod
    def _select_episodes(layout: LeRobotLayout, spec: ImportSpec) -> list[Episode]:
        available = [episode.index for episode in layout.episodes]
        selected = set(parse_episode_selection(spec.options.get("episodes"), available))
        return [episode for episode in layout.episodes if episode.index in selected]

    @staticmethod
    def _max_frames(spec: ImportSpec) -> int:
        return int(spec.options.get("max_frames_per_episode", 0) or 0)

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
        """One bundle per episode; frames extracted (default) or window rows emitted."""
        root = self._local_root(source)
        info = self.resolve_info(spec, source)
        layout = parse_layout(root)
        episodes = self._select_episodes(layout, spec)
        mode = self._frames_mode(spec)
        if source.kind == "hf_hub" and source.url:
            needed = {camera.video_path for episode in episodes for camera in episode.cameras.values()}
            if mode == "extract":
                needed |= {episode.data_path for episode in episodes if episode.data_path}
            root = materialize_files(source.url, sorted(needed))
        namespace = self.effective_namespace(spec, source)
        resolver = MediaResolver(spec.media, base_dir=root)
        resume_ordinal = int(cursor.get("episode_ordinal", 0)) if cursor else 0

        for ordinal, episode in enumerate(episodes, start=1):
            if ordinal <= resume_ordinal:
                continue
            record_id = stable_id(namespace, "train", episode.index)
            assert info.record is not None
            tables: dict[str, list[LanceModel]] = {
                "records": [
                    info.record(
                        id=record_id,
                        split="train",
                        episode_index=episode.index,
                        tasks=episode.tasks,
                        length=episode.length,
                    )
                ]
            }
            data_rows = self._episode_rows(root, layout, episode) if mode == "extract" else []
            if data_rows and info.timeseries is not None and layout.feature_dims:
                from pixano.utils import to_snake_case

                cap = self._max_frames(spec)
                selected = data_rows
                if cap and len(selected) > cap:
                    stride = len(selected) / cap
                    selected = [selected[int(position * stride)] for position in range(cap)]
                series_rows = []
                for ordinal, data_row in enumerate(selected):
                    frame_index = int(data_row.get("frame_index", ordinal))
                    values = {
                        to_snake_case(key.replace(".", "_")): [float(v) for v in data_row.get(key, [])]
                        for key in layout.feature_dims
                    }
                    series_rows.append(
                        info.timeseries(
                            id=stable_id(record_id, "ts", frame_index),
                            record_id=record_id,
                            frame_index=frame_index,
                            timestamp=float(data_row.get("timestamp", ordinal)),
                            **values,
                        )
                    )
                tables["timeseries"] = series_rows
            for key, camera in sorted(episode.cameras.items()):
                view_name = camera_view_name(key)
                shard = root / camera.video_path
                if mode == "extract":
                    rows = self._extract_frames(
                        info,
                        layout,
                        spec,
                        record_id,
                        view_name,
                        shard,
                        camera.from_timestamp,
                        camera.to_timestamp,
                        data_rows,
                    )
                else:
                    rows = [self._video_row(info, layout, resolver, record_id, view_name, camera, shard, root)]
                for row in rows:
                    tables.setdefault(canonical_table_name_for_schema(type(row)), []).append(row)
            yield BatchBundle(
                tables=tables,
                cursor={"episode_ordinal": ordinal},
                provenance=Provenance(file=str(source.path), record_key=str(episode.index)),
            )

    @staticmethod
    def _episode_rows(root: Path, layout: LeRobotLayout, episode: "Episode") -> list[dict]:
        """The episode's data-parquet rows (timestamp + float features), frame order.

        These per-row timestamps are LeRobot's ground truth — the values
        `delta_timestamps` indexes against — so frames and vectors align 1:1.
        """
        import pyarrow.parquet as pq

        data_file = root / episode.data_path
        if not data_file.is_file():
            raise MetadataError(f"Episode data parquet not found: {data_file}")
        available = set(pq.read_schema(data_file).names)
        columns = [name for name in ("timestamp", "frame_index", *layout.feature_dims) if name in available]
        filters = [("episode_index", "==", episode.index)] if "episode_index" in available else None
        table = pq.read_table(data_file, columns=columns, filters=filters)
        rows = table.to_pylist()
        rows.sort(key=lambda row: row.get("frame_index", row.get("timestamp", 0.0)))
        if not rows:
            raise MetadataError(f"No data rows for episode {episode.index} in {data_file}.")
        return rows

    def _extract_frames(
        self,
        info: DatasetInfo,
        layout: LeRobotLayout,
        spec: ImportSpec,
        record_id: str,
        view_name: str,
        shard: Path,
        from_timestamp: float,
        to_timestamp: float,
        data_rows: list[dict],
    ) -> list[LanceModel]:
        if not shard.is_file():
            raise MetadataError(f"Video shard not found: {shard}")
        probe = probe_video(shard)
        fps = layout.fps or probe.fps
        if not fps:
            raise MetadataError(f"No fps in meta/info.json or the probe for '{shard.name}'.")

        with tempfile.TemporaryDirectory(prefix="pixano-lerobot-") as tmp:
            command = ["ffmpeg", "-nostdin", "-v", "error"]
            if from_timestamp > 0:
                command += ["-ss", f"{from_timestamp:.6f}"]
            command += ["-i", str(shard)]
            if to_timestamp > 0:
                command += ["-t", f"{to_timestamp - from_timestamp:.6f}"]
            # Passthrough: every encoded frame, no resampling — frame k sits at
            # window time k/fps, and rows map onto frames by their own timestamps.
            command += ["-fps_mode", "passthrough", "-q:v", "2", f"{tmp}/%06d.jpg"]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0 and "fps_mode" in (result.stderr or ""):
                command[command.index("-fps_mode")] = "-vsync"  # pre-5.1 ffmpeg
                result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise MetadataError(f"ffmpeg frame extraction failed on '{shard.name}': {result.stderr.strip()[:200]}")

            frame_files = sorted(Path(tmp).glob("*.jpg"))
            # LeRobot's delta_timestamps discipline: row timestamps must sit ON
            # the decoded frame grid (default tolerance_s=1e-4, like LeRobot).
            tolerance = float(spec.options.get("tolerance_s", 1e-4))
            selected = data_rows
            cap = self._max_frames(spec)
            if cap and len(selected) > cap:
                stride = len(selected) / cap
                selected = [selected[int(position * stride)] for position in range(cap)]

            view_cls = info.views[view_name]
            rows: list[LanceModel] = []
            for ordinal, data_row in enumerate(selected):
                row_timestamp = float(data_row.get("timestamp", ordinal / fps))
                k = round(row_timestamp * fps)
                if abs(k / fps - row_timestamp) > tolerance:
                    raise MetadataError(
                        f"timestamp_alignment: row t={row_timestamp:.6f}s is not on the {fps}fps frame grid "
                        f"of '{shard.name}' (off by {abs(k / fps - row_timestamp):.6f}s > tolerance {tolerance}s). "
                        "Set options.tolerance_s to relax."
                    )
                if not 0 <= k < len(frame_files):
                    raise MetadataError(
                        f"timestamp_alignment: row t={row_timestamp:.6f}s maps to frame {k} but "
                        f"'{shard.name}' window decoded {len(frame_files)} frames."
                    )
                frame_index = int(data_row.get("frame_index", ordinal))
                rows.append(
                    view_cls(
                        id=stable_id(record_id, "view", view_name, frame_index),
                        record_id=record_id,
                        logical_name=view_name,
                        uri="",
                        raw_bytes=frame_files[k].read_bytes(),
                        width=probe.width,
                        height=probe.height,
                        format="JPEG",
                        frame_index=frame_index,
                        timestamp=row_timestamp,
                    )
                )
            return rows

    def _video_row(
        self,
        info: DatasetInfo,
        layout: LeRobotLayout,
        resolver: MediaResolver,
        record_id: str,
        view_name: str,
        camera: object,
        shard: Path,
        root: Path,
    ) -> LanceModel:
        from .layout import EpisodeCamera

        assert isinstance(camera, EpisodeCamera)
        resolved = resolver.resolve(str(shard.relative_to(root)))
        width = height = 0
        num_frames = 0
        duration = 0.0
        fps = layout.fps
        if shard.is_file() and ffprobe_available():
            probe = probe_video(shard)
            width, height, fps = probe.width, probe.height, layout.fps or probe.fps
            duration = camera.to_timestamp - camera.from_timestamp if camera.to_timestamp > 0 else probe.duration
            num_frames = int(duration * fps) if fps else probe.num_frames
        view_cls = info.views[view_name]
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
            format=shard.suffix.removeprefix("."),
            from_timestamp=camera.from_timestamp,
            to_timestamp=camera.to_timestamp,
        )


def _detect(source: SourceRef) -> DetectResult | None:
    return LeRobotImporter().probe(source)


LEROBOT = DataFormat(
    name="lerobot",
    title="LeRobot (v2.1 / v3)",
    importer_cls=LeRobotImporter,
    capabilities=Capabilities(
        media_kinds=frozenset({"sequence_frames", "video"}),
        annotation_kinds=frozenset(),
        source_kinds=frozenset({"local_dir"}),
        supports_resume=True,
        deterministic_ids=True,
    ),
    detect=_detect,
)
