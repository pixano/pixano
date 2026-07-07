# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import FORMATS, ImportSpec, SourceRef, ffmpeg_available, ffprobe_available, import_dataset
from pixano.datasets.io.formats.lerobot import LeRobotImporter
from pixano.datasets.io.formats.lerobot.layout import parse_episode_selection, parse_layout
from tests.assets.sample_data.metadata import VIDEO_MP4_ASSET_URL, VIDEO_MP4_METADATA


needs_ffmpeg = pytest.mark.skipif(
    not (ffmpeg_available() and ffprobe_available()), reason="ffmpeg/ffprobe not installed"
)

CAMERA_KEY = "observation.images.top"
FPS = VIDEO_MP4_METADATA["fps"]


def make_v21_dataset(root: Path, episodes: int = 2) -> Path:
    """Synthetic v2.1 layout: one video file per episode (copies of the sample video)."""
    (root / "meta").mkdir(parents=True)
    info = {
        "codebase_version": "v2.1",
        "robot_type": "so100",
        "fps": FPS,
        "chunks_size": 1000,
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {CAMERA_KEY: {"dtype": "video"}, "action": {"dtype": "float32"}},
        "total_episodes": episodes,
    }
    (root / "meta" / "info.json").write_text(json.dumps(info))
    lines = [
        json.dumps({"episode_index": index, "tasks": [f"task {index}"], "length": 100 + index})
        for index in range(episodes)
    ]
    (root / "meta" / "episodes.jsonl").write_text("\n".join(lines) + "\n")
    for index in range(episodes):
        target = root / "videos" / "chunk-000" / CAMERA_KEY / f"episode_{index:06d}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(VIDEO_MP4_ASSET_URL, target)
    return root


def make_v3_dataset(root: Path) -> Path:
    """Synthetic v3 layout: two episodes as windows into one shared video shard."""
    (root / "meta" / "episodes" / "chunk-000").mkdir(parents=True)
    info = {
        "codebase_version": "v3.0",
        "fps": FPS,
        "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
        "features": {CAMERA_KEY: {"dtype": "video"}},
        "total_episodes": 2,
    }
    (root / "meta" / "info.json").write_text(json.dumps(info))
    table = pa.table(
        {
            "episode_index": [0, 1],
            "tasks": [["pick"], ["place"]],
            "length": [90, 88],
            f"videos/{CAMERA_KEY}/chunk_index": [0, 0],
            f"videos/{CAMERA_KEY}/file_index": [0, 0],
            f"videos/{CAMERA_KEY}/from_timestamp": [0.0, 3.0],
            f"videos/{CAMERA_KEY}/to_timestamp": [3.0, 6.5],
        }
    )
    pq.write_table(table, root / "meta" / "episodes" / "chunk-000" / "file-000.parquet")
    shard = root / "videos" / CAMERA_KEY / "chunk-000" / "file-000.mp4"
    shard.parent.mkdir(parents=True)
    shutil.copy(VIDEO_MP4_ASSET_URL, shard)
    return root


def _spec(name: str, **options) -> ImportSpec:
    return ImportSpec.model_validate(
        {
            "dataset": {"name": name, "workspace": "video"},
            "format": "lerobot",
            "ids": {"namespace": "lr"},
            "options": options,
        }
    )


class TestLayoutParsing:
    def test_v21_layout(self, tmp_path: Path):
        layout = parse_layout(make_v21_dataset(tmp_path / "ds"))
        assert layout.version == "v2.1" and layout.video_keys == [CAMERA_KEY]
        assert [episode.index for episode in layout.episodes] == [0, 1]
        camera = layout.episodes[1].cameras[CAMERA_KEY]
        assert camera.video_path.endswith("episode_000001.mp4")
        assert camera.to_timestamp == -1.0  # whole file

    def test_v3_layout_windows(self, tmp_path: Path):
        layout = parse_layout(make_v3_dataset(tmp_path / "ds"))
        cameras = [episode.cameras[CAMERA_KEY] for episode in layout.episodes]
        assert (cameras[0].from_timestamp, cameras[0].to_timestamp) == (0.0, 3.0)
        assert (cameras[1].from_timestamp, cameras[1].to_timestamp) == (3.0, 6.5)
        assert cameras[0].video_path == cameras[1].video_path  # shared shard

    def test_episode_selection(self):
        assert parse_episode_selection(None, [0, 1, 2]) == [0, 1, 2]
        assert parse_episode_selection("1:2", [0, 1, 2]) == [1, 2]
        assert parse_episode_selection([2, 0], [0, 1, 2]) == [0, 2]


class TestLeRobotImport:
    def test_detection(self, tmp_path: Path):
        source = make_v21_dataset(tmp_path / "ds")
        assert FORMATS.detect(SourceRef.from_string(str(source))).name == "lerobot"

    @needs_ffmpeg
    def test_v21_extract_default(self, tmp_path: Path):
        source = make_v21_dataset(tmp_path / "ds")
        spec = _spec("lr_v21", max_frames_per_episode=8)
        result = import_dataset(source, tmp_path / "data", spec, importer=LeRobotImporter())
        dataset = Dataset(result.dataset_path)

        assert dataset.open_table("records").count_rows() == 2
        assert dataset.open_table("sequence_frames").count_rows() == 16  # 8 per episode (capped)
        record = sorted(dataset.get_data("records"), key=lambda r: r.episode_index)[0]
        assert record.tasks == ["task 0"] and record.length == 100
        frame_row = (
            dataset.open_table("sequence_frames")
            .search()
            .select(["raw_bytes", "format", "preview"])
            .limit(1)
            .to_list()[0]
        )
        assert frame_row["raw_bytes"] and frame_row["format"] == "JPEG"
        assert frame_row["preview"]  # engine-stamped grid thumbnail
        assert dataset.info.storage_mode == "embedded"

    @needs_ffmpeg
    def test_v3_windows_extract_disjoint_frames(self, tmp_path: Path):
        source = make_v3_dataset(tmp_path / "ds")
        spec = _spec("lr_v3", max_frames_per_episode=6)
        result = import_dataset(source, tmp_path / "data", spec, importer=LeRobotImporter())
        dataset = Dataset(result.dataset_path)

        assert dataset.open_table("records").count_rows() == 2
        assert dataset.open_table("sequence_frames").count_rows() == 12
        frames = dataset.get_data("sequence_frames", limit=20)
        by_record: dict[str, list[float]] = {}
        for frame in frames:
            by_record.setdefault(frame.record_id, []).append(frame.timestamp)
        first, second = sorted(by_record.values(), key=min)
        assert max(first) < 3.05 and min(second) >= 2.95  # windows respected

    @needs_ffmpeg
    def test_episode_subset_and_idempotent_rerun(self, tmp_path: Path):
        source = make_v21_dataset(tmp_path / "ds")
        spec = _spec("lr_subset", episodes=[1], max_frames_per_episode=4)
        result = import_dataset(source, tmp_path / "data", spec, importer=LeRobotImporter())
        dataset = Dataset(result.dataset_path)
        assert dataset.open_table("records").count_rows() == 1
        assert dataset.get_data("records")[0].episode_index == 1

        add_spec = spec.model_copy(update={"mode": "add"})
        import_dataset(source, tmp_path / "data", add_spec, importer=LeRobotImporter())
        assert dataset.open_table("records").count_rows() == 1
        assert dataset.open_table("sequence_frames").count_rows() == 4

    @needs_ffmpeg
    def test_reference_mode_emits_video_windows(self, tmp_path: Path):
        source = make_v3_dataset(tmp_path / "ds")
        spec = _spec("lr_ref", frames="reference")
        result = import_dataset(source, tmp_path / "data", spec, importer=LeRobotImporter())
        dataset = Dataset(result.dataset_path)

        assert dataset.open_table("records").count_rows() == 2
        videos = sorted(
            dataset.open_table("videos").search().select(["from_timestamp", "to_timestamp", "raw_bytes"]).to_list(),
            key=lambda video: video["from_timestamp"],
        )
        assert [video["to_timestamp"] for video in videos] == [3.0, 6.5]
        assert videos[0]["raw_bytes"]  # embed mode: shard bytes stored

    def test_analyze_reports_plan(self, tmp_path: Path):
        source = make_v21_dataset(tmp_path / "ds")
        plan = LeRobotImporter().analyze(
            SourceRef.from_string(str(source)),
            _spec("lr_plan", max_frames_per_episode=8),
            __import__("pixano.datasets.io.plan", fromlist=["AnalyzeLimits"]).AnalyzeLimits(),
        )
        assert plan.totals.records == 2
        assert plan.report.is_valid
        if ffprobe_available():
            assert (plan.totals.media_bytes or 0) > 0  # extract-size estimate present

    def test_invalid_frames_mode_rejected(self, tmp_path: Path):
        from pixano.datasets.io.errors import MetadataError

        source = make_v21_dataset(tmp_path / "ds")
        with pytest.raises(MetadataError, match="frames mode"):
            LeRobotImporter().analyze(
                SourceRef.from_string(str(source)),
                _spec("lr_bad", frames="explode"),
                __import__("pixano.datasets.io.plan", fromlist=["AnalyzeLimits"]).AnalyzeLimits(),
            )


class TestHubSource:
    @pytest.fixture()
    def fake_hub(self, tmp_path: Path, monkeypatch):
        """A synthetic v2.1 dataset served through mocked hub materialization."""
        dataset_root = make_v21_dataset(tmp_path / "hub_ds")
        calls: dict[str, list] = {"meta": [], "files": []}

        def fake_meta(repo_id: str, revision=None) -> Path:
            calls["meta"].append(repo_id)
            return dataset_root

        def fake_files(repo_id: str, relative_paths: list[str], revision=None) -> Path:
            calls["files"].append(sorted(relative_paths))
            return dataset_root

        import pixano.datasets.io.formats.lerobot.importer as importer_module

        monkeypatch.setattr(importer_module, "materialize_meta", fake_meta)
        monkeypatch.setattr(importer_module, "materialize_files", fake_files)
        return calls

    def test_analyze_is_meta_only(self, fake_hub):
        plan = LeRobotImporter().analyze(
            SourceRef.from_string("hub://acme/robo"),
            _spec("hub_plan"),
            __import__("pixano.datasets.io.plan", fromlist=["AnalyzeLimits"]).AnalyzeLimits(),
        )
        assert plan.totals.records == 2 and plan.report.is_valid
        assert fake_hub["meta"] == ["acme/robo"]
        assert fake_hub["files"] == []  # no shard downloads at analyze

    @needs_ffmpeg
    def test_ingest_downloads_only_selected_episodes(self, fake_hub, tmp_path: Path):
        spec = _spec("hub_subset", episodes=[1], max_frames_per_episode=4)
        result = import_dataset("hub://acme/robo", tmp_path / "data", spec, importer=LeRobotImporter())

        assert fake_hub["files"] == [[f"videos/chunk-000/{CAMERA_KEY}/episode_000001.mp4"]]
        dataset = Dataset(result.dataset_path)
        assert dataset.open_table("records").count_rows() == 1
        assert dataset.get_data("records")[0].episode_index == 1

    def test_missing_hf_hub_is_a_typed_error(self, monkeypatch):
        import pixano.datasets.io.formats.lerobot.hub as hub_module

        monkeypatch.setattr(hub_module, "_require_hf_hub", hub_module._require_hf_hub)
        monkeypatch.setitem(__import__("sys").modules, "huggingface_hub", None)
        # is_hub_id stays available without the dependency
        assert hub_module.is_hub_id("lerobot/pusht")
        assert not hub_module.is_hub_id("not a hub id")
        assert not hub_module.is_hub_id("/absolute/path")


class TestWorkspaceDefault:
    @needs_ffmpeg
    def test_bare_spec_defaults_to_video_workspace(self, tmp_path: Path):
        from pixano.datasets.workspaces import WorkspaceType

        source = make_v21_dataset(tmp_path / "ds")
        spec = ImportSpec.model_validate({"format": "lerobot", "options": {"max_frames_per_episode": 2}})
        result = import_dataset(source, tmp_path / "data", spec, importer=LeRobotImporter())
        assert Dataset(result.dataset_path).info.workspace == WorkspaceType.VIDEO

    def test_explicit_workspace_wins(self, tmp_path: Path):
        from pixano.datasets.io import SourceRef
        from pixano.datasets.workspaces import WorkspaceType

        source = make_v21_dataset(tmp_path / "ds")
        spec = ImportSpec.model_validate({"format": "lerobot", "dataset": {"name": "x", "workspace": "image_vqa"}})
        info = LeRobotImporter().resolve_info(spec, SourceRef.from_string(str(source)))
        assert info.workspace == WorkspaceType.IMAGE_VQA
