# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""LeRobot dataset layout parsing — pyarrow-only, no `lerobot` dependency (spec §7.3).

Supports the v2.1 layout (one parquet/video file per episode) and the v3
layout (episodes concatenated into shard files, located through the episodes
metadata parquet with per-camera time windows).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ...errors import MetadataError
from ...plan import Provenance


@dataclass
class EpisodeCamera:
    """Where one camera's footage for one episode lives."""

    video_path: str  # relative to the dataset root
    from_timestamp: float = 0.0
    to_timestamp: float = -1.0  # -1 = whole file (v2.1)


@dataclass
class Episode:
    """One episode: record attrs plus per-camera video and data references."""

    index: int
    tasks: list[str] = field(default_factory=list)
    length: int = 0
    cameras: dict[str, EpisodeCamera] = field(default_factory=dict)
    data_path: str = ""  # parquet holding this episode's rows, relative to the root


@dataclass
class LeRobotLayout:
    """Parsed dataset structure shared by analyze and ingest."""

    version: str
    fps: float
    video_keys: list[str]
    episodes: list[Episode]
    robot_type: str = ""
    feature_dims: dict[str, int] = field(default_factory=dict)  # 1-D float features -> vector dim


_BOOKKEEPING_KEYS = frozenset({"timestamp", "frame_index", "episode_index", "index", "task_index"})


def float_feature_dims(info: dict) -> dict[str, int]:
    """1-D float features (action, observation.state, ...) -> vector dim, bookkeeping excluded."""
    dims: dict[str, int] = {}
    for key, feature in (info.get("features", {}) or {}).items():
        shape = feature.get("shape") or []
        if key in _BOOKKEEPING_KEYS or feature.get("dtype") not in ("float32", "float64"):
            continue
        if len(shape) == 1 and int(shape[0]) > 1:
            dims[key] = int(shape[0])
    return dims


def camera_view_name(video_key: str) -> str:
    """Short logical view name for a camera key ('observation.images.top' -> 'top')."""
    return video_key.rsplit(".", 1)[-1]


def parse_layout(root: Path) -> LeRobotLayout:
    """Parse meta/info.json and the episode metadata for v2.1 or v3 layouts."""
    info_path = root / "meta" / "info.json"
    if not info_path.is_file():
        raise MetadataError("Not a LeRobot dataset: meta/info.json is missing.", Provenance(file=str(root)))
    info = json.loads(info_path.read_text(encoding="utf-8"))
    version = str(info.get("codebase_version", ""))
    fps = float(info.get("fps", 0) or 0)
    features = info.get("features", {}) or {}
    video_keys = sorted(key for key, feature in features.items() if feature.get("dtype") == "video")

    if version.startswith("v3"):
        episodes = _parse_v3_episodes(root, info, video_keys)
    elif version.startswith("v2"):
        episodes = _parse_v21_episodes(root, info, video_keys)
    else:
        raise MetadataError(
            f"Unsupported LeRobot codebase_version '{version}' (supported: v2.x, v3.x).",
            Provenance(file=str(info_path)),
        )
    return LeRobotLayout(
        version=version,
        fps=fps,
        video_keys=video_keys,
        episodes=episodes,
        robot_type=str(info.get("robot_type", "") or ""),
        feature_dims=float_feature_dims(info),
    )


def _parse_v21_episodes(root: Path, info: dict, video_keys: list[str]) -> list[Episode]:
    episodes_file = root / "meta" / "episodes.jsonl"
    if not episodes_file.is_file():
        raise MetadataError("v2.1 layout: meta/episodes.jsonl is missing.", Provenance(file=str(episodes_file)))
    template = str(
        info.get("video_path", "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4")
    )
    data_template = str(info.get("data_path", "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet"))
    chunks_size = int(info.get("chunks_size", 1000) or 1000)

    episodes: list[Episode] = []
    for line in episodes_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        index = int(payload["episode_index"])
        cameras = {
            key: EpisodeCamera(
                video_path=template.format(episode_chunk=index // chunks_size, video_key=key, episode_index=index)
            )
            for key in video_keys
        }
        tasks = payload.get("tasks", [])
        episodes.append(
            Episode(
                index=index,
                tasks=list(tasks) if isinstance(tasks, list) else [str(tasks)],
                length=int(payload.get("length", 0) or 0),
                cameras=cameras,
                data_path=data_template.format(episode_chunk=index // chunks_size, episode_index=index),
            )
        )
    return sorted(episodes, key=lambda episode: episode.index)


def _parse_v3_episodes(root: Path, info: dict, video_keys: list[str]) -> list[Episode]:
    import pyarrow.parquet as pq

    episodes_dir = root / "meta" / "episodes"
    parquet_files = sorted(episodes_dir.rglob("*.parquet"))
    if not parquet_files:
        raise MetadataError("v3 layout: no parquet files under meta/episodes/.", Provenance(file=str(episodes_dir)))
    template = str(info.get("video_path", "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"))
    data_template = str(info.get("data_path", "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"))

    episodes: list[Episode] = []
    for parquet_file in parquet_files:
        table = pq.read_table(parquet_file)
        rows = table.to_pylist()
        for payload in rows:
            index = int(payload["episode_index"])
            cameras: dict[str, EpisodeCamera] = {}
            for key in video_keys:
                cameras[key] = EpisodeCamera(
                    video_path=template.format(
                        video_key=key,
                        chunk_index=int(payload.get(f"videos/{key}/chunk_index", 0) or 0),
                        file_index=int(payload.get(f"videos/{key}/file_index", 0) or 0),
                    ),
                    from_timestamp=float(payload.get(f"videos/{key}/from_timestamp", 0.0) or 0.0),
                    to_timestamp=float(payload.get(f"videos/{key}/to_timestamp", -1.0) or -1.0),
                )
            tasks = payload.get("tasks", [])
            episodes.append(
                Episode(
                    index=index,
                    tasks=list(tasks) if isinstance(tasks, list) else [str(tasks)],
                    length=int(payload.get("length", 0) or 0),
                    cameras=cameras,
                    data_path=data_template.format(
                        chunk_index=int(payload.get("data/chunk_index", 0) or 0),
                        file_index=int(payload.get("data/file_index", 0) or 0),
                    ),
                )
            )
    return sorted(episodes, key=lambda episode: episode.index)


def parse_episode_selection(selection: object, available: list[int]) -> list[int]:
    """Resolve the `episodes` option: a list of ints or an inclusive 'start:end' range."""
    if selection is None:
        return available
    if isinstance(selection, str):
        start_str, _, end_str = selection.partition(":")
        start = int(start_str) if start_str else min(available, default=0)
        end = int(end_str) if end_str else max(available, default=-1)
        return [index for index in available if start <= index <= end]
    if isinstance(selection, (list, tuple)):
        wanted = {int(value) for value in selection}
        return [index for index in available if index in wanted]
    raise MetadataError(f"Invalid episodes selection: {selection!r} (list of ints or 'start:end').")
