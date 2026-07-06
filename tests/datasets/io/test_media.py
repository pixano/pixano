# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest

from pixano.datasets.io import MediaPolicy, MediaResolutionError, MediaResolver, ffprobe_available, probe_image
from pixano.datasets.io.media import probe_video
from tests.assets.sample_data.metadata import (
    IMAGE_JPG_ASSET_URL,
    IMAGE_JPG_METADATA,
    VIDEO_MP4_ASSET_URL,
    VIDEO_MP4_METADATA,
)


needs_ffprobe = pytest.mark.skipif(not ffprobe_available(), reason="ffprobe not installed")


class TestProbes:
    @needs_ffprobe
    def test_probe_video_matches_ground_truth(self):
        probe = probe_video(VIDEO_MP4_ASSET_URL)
        assert probe.width == VIDEO_MP4_METADATA["width"]
        assert probe.height == VIDEO_MP4_METADATA["height"]
        assert probe.num_frames == VIDEO_MP4_METADATA["num_frames"]
        assert probe.fps == pytest.approx(VIDEO_MP4_METADATA["fps"], abs=0.01)
        assert probe.duration == pytest.approx(VIDEO_MP4_METADATA["duration"], abs=0.01)
        assert probe.format == "mp4"

    @needs_ffprobe
    def test_probe_video_is_cached(self, monkeypatch):
        probe_video(VIDEO_MP4_ASSET_URL)  # warm the cache

        def _no_subprocess(*args, **kwargs):
            raise AssertionError("subprocess should not run on a cache hit")

        monkeypatch.setattr("pixano.datasets.io.media.subprocess.run", _no_subprocess)
        probe = probe_video(VIDEO_MP4_ASSET_URL)
        assert probe.width == VIDEO_MP4_METADATA["width"]

    def test_probe_video_missing_file(self, tmp_path: Path):
        with pytest.raises(MediaResolutionError, match="not found"):
            probe_video(tmp_path / "ghost.mp4")

    def test_probe_image(self):
        width, height, image_format = probe_image(IMAGE_JPG_ASSET_URL)
        assert (width, height, image_format) == (
            IMAGE_JPG_METADATA["width"],
            IMAGE_JPG_METADATA["height"],
            IMAGE_JPG_METADATA["format"],
        )


class TestMediaResolver:
    def test_embed_reads_local_bytes(self):
        resolver = MediaResolver(MediaPolicy(mode="embed"), base_dir=IMAGE_JPG_ASSET_URL.parent)
        resolved = resolver.resolve(IMAGE_JPG_ASSET_URL.name)
        assert resolved.uri == ""
        assert len(resolved.raw_bytes) == IMAGE_JPG_ASSET_URL.stat().st_size

    def test_embed_rejects_remote_uri(self):
        resolver = MediaResolver(MediaPolicy(mode="embed"))
        with pytest.raises(MediaResolutionError, match="not embeddable"):
            resolver.resolve("https://example.com/img.jpg")

    def test_embed_missing_file(self, tmp_path: Path):
        resolver = MediaResolver(MediaPolicy(mode="embed"), base_dir=tmp_path)
        with pytest.raises(MediaResolutionError, match="not found"):
            resolver.resolve("ghost.jpg")

    def test_uri_passes_remote_through(self):
        resolver = MediaResolver(MediaPolicy(mode="uri"))
        assert resolver.resolve("https://example.com/img.jpg").uri == "https://example.com/img.jpg"
        assert resolver.resolve("s3://bucket/key.jpg").uri == "s3://bucket/key.jpg"

    def test_uri_rejects_bare_local_path(self):
        # Browsers cannot fetch server-side paths; the error points at embed mode (spec §6).
        resolver = MediaResolver(MediaPolicy(mode="uri"))
        with pytest.raises(MediaResolutionError, match="embed"):
            resolver.resolve("images/0001.jpg")

    def test_uri_prefix_rewrites_relative_paths(self):
        resolver = MediaResolver(MediaPolicy(mode="uri", uri_prefix="https://cdn.example.com/ds/"))
        assert resolver.resolve("images/0001.jpg").uri == "https://cdn.example.com/ds/images/0001.jpg"


class TestCreateVideoUsesProbe:
    @needs_ffprobe
    def test_create_video_probes_missing_fields(self):
        from pixano.schemas import create_video

        video = create_video(VIDEO_MP4_ASSET_URL, id="v1", record_id="r1", logical_name="video")
        assert video.width == VIDEO_MP4_METADATA["width"]
        assert video.num_frames == VIDEO_MP4_METADATA["num_frames"]
        assert video.from_timestamp == 0.0
        assert video.to_timestamp == -1.0
