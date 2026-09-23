# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Media resolution and probing under the two storage modes (spec §6).

- ``embed`` (default): local paths are read once into ``raw_bytes``; nothing
  is copied or managed on the server side.
- ``uri``: rows store the URI verbatim (``http(s)://`` fully supported;
  ``s3://`` accepted — browser viewing needs user-side serving). Bare local
  paths are a validation error in uri mode: they are not fetchable by a
  browser; the error points at embed mode.

``probe_video`` shells out to the ``ffprobe`` binary (JSON output) — no
Python ffmpeg dependency — and caches per distinct file so shared media
(e.g. LeRobot shards) is probed once, not per row.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import MediaResolutionError
from .plan import Provenance
from .spec import MediaPolicy


_REMOTE_SCHEMES = ("http://", "https://", "s3://")


@dataclass(frozen=True)
class VideoProbe:
    """Technical metadata of a video file."""

    width: int
    height: int
    fps: float
    num_frames: int
    duration: float
    codec: str
    format: str


@dataclass(frozen=True)
class ResolvedMedia:
    """Constructor payload for a View row: exactly one of uri / raw_bytes is set."""

    uri: str = ""
    raw_bytes: bytes = b""


def ffmpeg_available() -> bool:
    """True when the ffmpeg binary is on PATH (frame extraction, clip embedding)."""
    return shutil.which("ffmpeg") is not None


def ffprobe_available() -> bool:
    """Whether the ffprobe binary is on PATH."""
    return shutil.which("ffprobe") is not None


_probe_cache: dict[tuple[str, float, int], VideoProbe] = {}


def probe_video(path: Path) -> VideoProbe:
    """Probe a video file with ffprobe, cached per (path, mtime, size)."""
    try:
        stat = path.stat()
    except OSError:
        raise MediaResolutionError(f"Video file not found: {path}") from None
    cache_key = (str(path.resolve()), stat.st_mtime, stat.st_size)
    cached = _probe_cache.get(cache_key)
    if cached is not None:
        return cached

    if not ffprobe_available():
        raise MediaResolutionError(
            "ffprobe is required to probe video metadata but was not found on PATH. Install ffmpeg."
        )
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise MediaResolutionError(f"ffprobe failed on {path}: {result.stderr.strip()[:200]}")

    try:
        payload = json.loads(result.stdout)
        stream = next(s for s in payload["streams"] if s.get("codec_type") == "video")
        numerator, _, denominator = stream["r_frame_rate"].partition("/")
        fps = float(numerator) / float(denominator or 1)
        duration = float(stream.get("duration") or payload["format"]["duration"])
        num_frames = int(stream.get("nb_frames") or round(duration * fps))
        probe = VideoProbe(
            width=int(stream["width"]),
            height=int(stream["height"]),
            fps=fps,
            num_frames=num_frames,
            duration=duration,
            codec=str(stream.get("codec_name", "")),
            format=path.suffix.removeprefix("."),
        )
    except (KeyError, StopIteration, ValueError, ZeroDivisionError) as exc:
        raise MediaResolutionError(f"Could not parse ffprobe output for {path}: {exc}") from None

    _probe_cache[cache_key] = probe
    return probe


def probe_image(path: Path) -> tuple[int, int, str]:
    """Return (width, height, format) of an image file."""
    import PIL.Image

    try:
        with PIL.Image.open(path) as image:
            return image.width, image.height, str(image.format or "")
    except Exception as exc:
        raise MediaResolutionError(f"Could not probe image {path}: {exc}") from None


def probe_videos(paths: Iterable[Path], max_workers: int = 4) -> dict[Path, VideoProbe]:
    """Probe several videos concurrently (cache-aware)."""
    unique_paths = list(dict.fromkeys(paths))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        probes = list(pool.map(probe_video, unique_paths))
    return dict(zip(unique_paths, probes))


class MediaResolver:
    """Resolve metadata media values into View constructor payloads under a policy.

    Relative paths resolve against the metadata file's directory only
    (``base_dir``) — the dual-root leniency of the v1 folder import is gone.
    """

    def __init__(self, policy: MediaPolicy, base_dir: Path | None = None):
        """Initialize with the media policy and the metadata file's directory."""
        self.policy = policy
        self.base_dir = base_dir

    def resolve(self, value: str, provenance: Provenance | None = None) -> ResolvedMedia:
        """Resolve one media value per the active mode (spec §6)."""
        is_remote = value.startswith(_REMOTE_SCHEMES)

        if self.policy.mode == "embed":
            if is_remote:
                # Remote URIs pass through verbatim: mixed datasets (embedded local
                # media + datalake URIs) are legal and stamped "mixed" (spec §6).
                return ResolvedMedia(uri=value)
            path = self._local_path(value, provenance)
            return ResolvedMedia(raw_bytes=path.read_bytes())

        # uri mode
        if is_remote:
            return ResolvedMedia(uri=value)
        if self.policy.uri_prefix:
            return ResolvedMedia(uri=f"{self.policy.uri_prefix.rstrip('/')}/{value.lstrip('/')}")
        raise MediaResolutionError(
            f"'{value}' is a local path, which browsers cannot fetch in media mode 'uri'. "
            "Use media mode 'embed' for local files, or provide uri_prefix / http(s) URIs.",
            provenance,
        )

    def local_path(self, value: str, provenance: Provenance | None = None) -> Path:
        """Resolve a local media path against base_dir (embed-mode file access, probing)."""
        return self._local_path(value, provenance)

    def _local_path(self, value: str, provenance: Provenance | None) -> Path:
        path = Path(value)
        if not path.is_absolute() and self.base_dir is not None:
            path = self.base_dir / path
        if not path.is_file():
            raise MediaResolutionError(f"Media file not found: {path}", provenance)
        return path


# Video container extensions accepted by the importers (relocated from the v1
# folder builders ahead of their deletion).
VIDEO_EXTENSIONS = [
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",
    ".vob",
]
