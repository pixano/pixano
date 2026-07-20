# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shutil
from pathlib import Path

import pytest

from pixano.datasets.io import FORMATS, ImportSpec, SourceRef, analyze, ffmpeg_available, ffprobe_available
from pixano.datasets.io.errors import MetadataError
from pixano.datasets.io.formats.pixano_jsonl import PixanoJsonlImporter
from pixano.datasets.io.formats.pixano_jsonl.media_only import discover_layout, is_media_only_source
from pixano.datasets.io.plan import PreflightReport
from pixano.datasets.io.testing import DatasetImporterTestCase
from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL, IMAGE_PNG_ASSET_URL, VIDEO_MP4_ASSET_URL


needs_ffmpeg = pytest.mark.skipif(
    not (ffmpeg_available() and ffprobe_available()), reason="ffmpeg/ffprobe not installed"
)


def _seed_images(directory: Path, stems: tuple[str, ...], asset: Path = IMAGE_JPG_ASSET_URL) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for stem in stems:
        shutil.copy(asset, directory / f"{stem}{asset.suffix}")


def _seed_frames(directory: Path, names: tuple[str, ...], asset: Path = IMAGE_JPG_ASSET_URL) -> None:
    """Copy the asset to full file NAMES (extension included) — frame folders control their names."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(asset, directory / name)


def _spec(payload: dict) -> ImportSpec:
    return ImportSpec.model_validate({"format": "pixano_jsonl", **payload})


class TestDiscovery:
    def test_flat_folder_is_media_only(self, tmp_path: Path):
        _seed_images(tmp_path, ("a", "b"))
        assert is_media_only_source(tmp_path)

    def test_jsonl_split_is_not_media_only(self, tmp_path: Path):
        (tmp_path / "train").mkdir()
        (tmp_path / "train" / "metadata.jsonl").write_text("{}\n", encoding="utf-8")
        assert not is_media_only_source(tmp_path)

    def test_split_and_view_dirs_mixed_is_ambiguous(self, tmp_path: Path):
        _seed_images(tmp_path / "train", ("a",))
        _seed_images(tmp_path / "extra", ("b",))
        report = PreflightReport()
        discover_layout(tmp_path, None, report)
        assert "ambiguous_media_layout" in report.findings

    def test_root_files_next_to_view_dirs_is_ambiguous(self, tmp_path: Path):
        _seed_images(tmp_path, ("root",))
        _seed_images(tmp_path / "left", ("a",))
        report = PreflightReport()
        discover_layout(tmp_path, None, report)
        assert "ambiguous_media_layout" in report.findings

    def test_mixed_kinds_in_one_folder(self, tmp_path: Path):
        _seed_images(tmp_path, ("a",))
        shutil.copy(VIDEO_MP4_ASSET_URL, tmp_path / "b.mp4")
        report = PreflightReport()
        discover_layout(tmp_path, None, report)
        assert "mixed_media_kinds" in report.findings

    def test_inconsistent_split_views(self, tmp_path: Path):
        _seed_images(tmp_path / "train" / "left", ("a",))
        _seed_images(tmp_path / "val" / "right", ("a",))
        report = PreflightReport()
        discover_layout(tmp_path, None, report)
        assert "inconsistent_split_views" in report.findings

    def test_declared_view_folder_missing(self, tmp_path: Path):
        _seed_images(tmp_path / "left", ("a",))
        report = PreflightReport()
        layout = discover_layout(tmp_path, {"left": "image", "right": "image"}, report)
        assert "view_folder_missing" in report.findings
        assert layout.total_records == 1  # the present view still imports

    def test_empty_folder_reports_no_media(self, tmp_path: Path):
        (tmp_path / "empty").mkdir()
        report = PreflightReport()
        discover_layout(tmp_path / "empty", None, report)
        assert "no_media_found" in report.findings

    def test_snake_cased_view_folders_match_declared_views(self, tmp_path: Path):
        _seed_images(tmp_path / "My-Left", ("a",))
        _seed_images(tmp_path / "My-Right", ("a",))
        report = PreflightReport()
        layout = discover_layout(tmp_path, {"my_left": "image", "my_right": "image"}, report)
        assert report.is_valid
        assert layout.total_records == 1
        assert set(layout.splits[0].records[0].files) == {"my_left", "my_right"}

    def test_inferred_view_folder_collision_is_reported(self, tmp_path: Path):
        """Two folders snake-casing to the same view must not silently drop one folder's files."""
        _seed_images(tmp_path / "Left Cam", ("a",))
        _seed_images(tmp_path / "left_cam", ("a",))
        report = PreflightReport()
        layout = discover_layout(tmp_path, None, report)
        assert "view_name_collision" in report.findings
        assert layout.total_records == 0  # ambiguous: nothing imports minus a view

    def test_declared_view_matched_by_two_folders_is_reported(self, tmp_path: Path):
        _seed_images(tmp_path / "Left Cam", ("a",))
        _seed_images(tmp_path / "left_cam", ("a",))
        report = PreflightReport()
        layout = discover_layout(tmp_path, {"left_cam": "image", "right": "image"}, report)
        assert "view_name_collision" in report.findings
        assert layout.total_records == 0

    def test_declared_split_named_view_is_rejected(self, tmp_path: Path):
        _seed_images(tmp_path / "train", ("a",))
        report = PreflightReport()
        layout = discover_layout(tmp_path, {"train": "image"}, report)
        assert "view_name_reserved" in report.findings
        assert layout.total_records == 0

    def test_single_declared_view_with_odd_subdirs_warns(self, tmp_path: Path):
        """The legacy every-subdir-is-a-split behavior stays, but stops being silent."""
        _seed_images(tmp_path / "day1", ("a",))
        _seed_images(tmp_path / "day2", ("b",))
        report = PreflightReport()
        layout = discover_layout(tmp_path, {"image": "image"}, report)
        assert report.findings["subdirs_treated_as_splits"].severity == "warning"
        assert report.is_valid  # a warning, not an error: the layout still imports
        assert {split.name for split in layout.splits} == {"day1", "day2"}
        assert layout.total_records == 2

    def test_flat_declared_view_duplicate_stems_are_reported(self, tmp_path: Path):
        """The legacy stem-keyed path detects a.jpg + a.png like inference does."""
        _seed_images(tmp_path, ("a",))
        _seed_images(tmp_path, ("a",), asset=IMAGE_PNG_ASSET_URL)
        report = PreflightReport()
        discover_layout(tmp_path, {"image": "image"}, report)
        assert "duplicate_view_stem" in report.findings


class TestRawImages:
    def test_flat_folder_inference(self, tmp_path: Path):
        source = tmp_path / "raw"
        _seed_images(source, ("a", "b", "c"))
        spec = _spec({"dataset": {"name": "flat"}})
        plan = analyze(source, spec)
        assert plan.report.is_valid
        assert plan.splits == {"default": 3}
        assert plan.inferred_schema["workspace"] == "image"
        assert plan.inferred_schema["views"]["image"]["base"] == "Image"
        assert plan.previews and plan.previews[0].thumbnails["image"].startswith("data:image/jpeg;base64,")
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(), source=source, spec=spec, expected_counts={"records": 3, "images": 3}
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_idempotent_rerun(dataset, tmp_path / "data")

    def test_multi_view_stem_matching(self, tmp_path: Path):
        source = tmp_path / "raw"
        _seed_images(source / "left", ("a", "b"))
        _seed_images(source / "right", ("a", "b"))
        _seed_images(source / "right", ("c",), asset=IMAGE_PNG_ASSET_URL)  # missing under left
        spec = _spec(
            {
                "dataset": {"name": "multi", "workspace": "image"},
                "schema": {"entity": {"attrs": {"category": "str"}}, "annotations": ["bbox"]},
            }
        )
        plan = analyze(source, spec)
        assert plan.splits == {"default": 3}
        assert set(plan.inferred_schema["views"]) == {"left", "right"}
        assert plan.inferred_schema["entity"]["fields"]["category"]["type"] == "str"
        assert "bbox" in plan.inferred_schema and "keypoint" not in plan.inferred_schema
        warning = plan.report.findings["missing_view_file"]
        assert warning.severity == "warning"
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(), source=source, spec=spec, expected_counts={"records": 3, "images": 5}
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_idempotent_rerun(dataset, tmp_path / "data")
        entities = dataset.open_table("entities").schema
        assert "category" in entities.names

    def test_split_dirs_with_nested_views(self, tmp_path: Path):
        source = tmp_path / "raw"
        for split in ("train", "val"):
            _seed_images(source / split / "left", ("a",))
            _seed_images(source / split / "right", ("a",))
        plan = analyze(source, _spec({"dataset": {"name": "splits"}}))
        assert plan.report.is_valid
        assert plan.splits == {"train": 1, "val": 1}
        assert set(plan.inferred_schema["views"]) == {"left", "right"}

    def test_legacy_split_layout_ids_are_stable(self, tmp_path: Path):
        """The pre-0.8.1 media-only shape (split dirs, single image view) keeps its ids."""
        source = tmp_path / "raw"
        _seed_images(source / "train", ("a", "b", "c"))
        spec = ImportSpec.model_validate({"dataset": {"name": "legacy", "workspace": "image"}})
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(), source=source, spec=spec, expected_counts={"records": 3, "images": 3}
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        records = sorted(row["id"] for row in dataset.open_table("records").search().select(["id"]).to_list())
        from pixano.datasets.io.ids import stable_id

        expected = sorted(
            stable_id("raw", "train", stem, ordinal) for ordinal, stem in enumerate(("a", "b", "c"), start=1)
        )
        assert records == expected

    def test_detection_of_raw_folder(self, tmp_path: Path):
        _seed_images(tmp_path / "raw", ("a",))
        detected = FORMATS.detect(SourceRef.from_string(str(tmp_path / "raw")))
        assert detected.name == "pixano_jsonl"


class TestRawVideos:
    @needs_ffmpeg
    def test_extract_frames_default_with_cap(self, tmp_path: Path):
        source = tmp_path / "vids"
        source.mkdir()
        for stem in ("v1", "v2"):
            shutil.copy(VIDEO_MP4_ASSET_URL, source / f"{stem}.mp4")
        spec = _spec({"dataset": {"name": "vids"}, "options": {"max_frames_per_video": 4}})
        plan = analyze(source, spec)
        assert plan.report.is_valid
        assert plan.inferred_schema["workspace"] == "video"
        assert plan.inferred_schema["views"]["video"]["base"] == "SequenceFrame"
        assert plan.media_size_estimate_bytes and plan.media_size_estimate_bytes > 0
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(),
            source=source,
            spec=spec,
            expected_counts={"records": 2, "sequence_frames": 8},
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_idempotent_rerun(dataset, tmp_path / "data")
        frames = dataset.open_table("sequence_frames").search().select(["frame_index", "timestamp"]).to_list()
        assert all(row["timestamp"] >= 0 for row in frames)

    @needs_ffmpeg
    def test_garbage_video_fails_analyze(self, tmp_path: Path):
        """An unprobeable video is an analyze error, not a silent empty record at ingest."""
        source = tmp_path / "vids"
        source.mkdir()
        shutil.copy(VIDEO_MP4_ASSET_URL, source / "ok.mp4")
        (source / "bad.mp4").write_bytes(b"not really a video")
        plan = analyze(source, _spec({"dataset": {"name": "vids"}}))
        assert "unreadable_video" in plan.report.findings
        assert not plan.report.is_valid

    @needs_ffmpeg
    def test_reference_mode_emits_video_rows(self, tmp_path: Path):
        source = tmp_path / "vids"
        source.mkdir()
        shutil.copy(VIDEO_MP4_ASSET_URL, source / "clip.mp4")
        spec = _spec({"dataset": {"name": "vidref"}, "options": {"frames": "reference"}})
        plan = analyze(source, spec)
        assert plan.inferred_schema["views"]["video"]["base"] == "Video"
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(), source=source, spec=spec, expected_counts={"records": 1, "videos": 1}
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        video = dataset.get_data("videos")[0]
        assert video.fps > 0 and video.to_timestamp == -1.0


def _seed_layout(root: Path, rel_files: list[str]) -> None:
    """Copy assets to relative paths — videos for .mp4 names, images otherwise."""
    for rel in rel_files:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(VIDEO_MP4_ASSET_URL if rel.endswith(".mp4") else IMAGE_JPG_ASSET_URL, target)


class TestVideoLayoutMatrix:
    """The eight acceptable raw-video layouts, pinned exactly as specified.

    Video files:   root/{split}/{views}/*.mp4 · root/{views}/*.mp4 ·
                   root/{split}/*.mp4 · root/*.mp4
    Frame folders: root/{split}/{views}/{video}/*.jpg · root/{views}/{video}/*.jpg ·
                   root/{split}/{video}/*.jpg · root/{video}/*.jpg
    """

    FILES_LAYOUTS = [
        (
            "split_views",
            ["train/front/a.mp4", "train/side/a.mp4", "val/front/b.mp4", "val/side/b.mp4"],
            {"train", "val"},
            2,
        ),
        ("views_only", ["front/a.mp4", "side/a.mp4"], {"default"}, 1),
        ("split_only", ["train/a.mp4", "val/b.mp4"], {"train", "val"}, 2),
        ("flat", ["a.mp4", "b.mp4"], {"default"}, 2),
    ]
    FOLDER_LAYOUTS = [
        (
            "split_views",
            ["train/front/v1/f0.jpg", "train/side/v1/f0.jpg", "val/front/v2/f0.jpg", "val/side/v2/f0.jpg"],
            {"train", "val"},
            2,
        ),
        ("views_only", ["front/v1/f0.jpg", "side/v1/f0.jpg"], {"default"}, 1),
        ("split_only", ["train/v1/f0.jpg", "val/v2/f0.jpg"], {"train", "val"}, 2),
        ("flat", ["v1/f0.jpg", "v2/f0.jpg"], {"default"}, 2),
    ]

    def _check(self, tmp_path: Path, files: list[str], options: dict, splits: set[str], records: int) -> None:
        source = tmp_path / "src"
        _seed_layout(source, files)
        spec = _spec({"dataset": {"name": "layout", "workspace": "video"}, "options": options})
        plan = analyze(source, spec)
        assert plan.report.is_valid, plan.report.findings
        assert set(plan.splits) == splits
        assert plan.totals.records == records
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(), source=source, spec=spec, expected_counts={"records": records}
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        assert dataset.open_table("sequence_frames").count_rows() > 0

    @needs_ffmpeg
    @pytest.mark.parametrize(("name", "files", "splits", "records"), FILES_LAYOUTS)
    def test_video_file_layouts(self, tmp_path: Path, name: str, files: list, splits: set, records: int):
        self._check(tmp_path, files, {"max_frames_per_video": 2}, splits, records)

    @pytest.mark.parametrize(("name", "files", "splits", "records"), FOLDER_LAYOUTS)
    def test_frame_folder_layouts(self, tmp_path: Path, name: str, files: list, splits: set, records: int):
        self._check(tmp_path, files, {"frames": "folders"}, splits, records)


class TestFrameFolders:
    """Pre-extracted frame folders: options {frames: folders} — no ffmpeg involved."""

    def test_single_view_folder_frames(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_frames(source / "clip_a", ("f0.jpg", "f1.jpg", "f2.jpg"))
        _seed_frames(source / "clip_b", ("f0.jpg", "f1.jpg"))
        spec = _spec({"dataset": {"name": "folders"}, "options": {"frames": "folders"}})
        plan = analyze(source, spec)
        assert plan.report.is_valid, plan.report.findings
        assert "ffmpeg_required" not in plan.report.findings
        assert not plan.media_size_estimate_bytes  # frames are already counted in media_bytes
        assert plan.totals.media_bytes and plan.totals.media_bytes > 0
        assert plan.splits == {"default": 2}
        assert plan.inferred_schema["workspace"] == "video"
        assert plan.inferred_schema["views"]["video"]["base"] == "SequenceFrame"
        assert plan.previews and plan.previews[0].thumbnails["video"].startswith("data:image/jpeg;base64,")
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(),
            source=source,
            spec=spec,
            expected_counts={"records": 2, "sequence_frames": 5},
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_idempotent_rerun(dataset, tmp_path / "data")
        frames = dataset.open_table("sequence_frames").search().select(["frame_index", "timestamp"]).to_list()
        assert all(row["timestamp"] == 0.0 for row in frames)  # no fps given

    def test_multi_view_split_folder_frames(self, tmp_path: Path):
        source = tmp_path / "vids"
        for split in ("train", "val"):
            for view in ("front", "side"):
                _seed_frames(source / split / view / "v1", ("f0.jpg", "f1.jpg"))
        spec = _spec(
            {
                "dataset": {"name": "mv", "workspace": "video"},
                "schema": {"views": {"front": "sequence_frames", "side": "sequence_frames"}},
                "options": {"frames": "folders"},
            }
        )
        plan = analyze(source, spec)
        assert plan.report.is_valid, plan.report.findings
        assert plan.splits == {"train": 1, "val": 1}
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(),
            source=source,
            spec=spec,
            expected_counts={"records": 2, "sequence_frames": 8},
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_idempotent_rerun(dataset, tmp_path / "data")

    def test_missing_video_in_one_view_warns(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_frames(source / "front" / "v1", ("f0.jpg", "f1.jpg"))
        _seed_frames(source / "front" / "v2", ("f0.jpg", "f1.jpg"))
        _seed_frames(source / "side" / "v1", ("f0.jpg", "f1.jpg"))
        spec = _spec({"dataset": {"name": "mv"}, "options": {"frames": "folders"}})
        plan = analyze(source, spec)
        assert plan.report.findings["missing_view_file"].severity == "warning"
        assert plan.report.is_valid
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(),
            source=source,
            spec=spec,
            expected_counts={"records": 2, "sequence_frames": 6},
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)

    def test_folder_frames_cap_keeps_original_indices(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_frames(source / "clip", tuple(f"f{i:02d}.jpg" for i in range(10)))
        spec = _spec({"dataset": {"name": "cap"}, "options": {"frames": "folders", "max_frames_per_video": 4}})
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(),
            source=source,
            spec=spec,
            expected_counts={"records": 1, "sequence_frames": 4},
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        frames = dataset.open_table("sequence_frames").search().select(["frame_index"]).to_list()
        assert sorted(row["frame_index"] for row in frames) == [0, 2, 5, 7]

    def test_folder_frames_lexicographic_order(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_frames(source / "clip", ("b_second.jpg",))
        _seed_frames(source / "clip", ("a_first.png",), asset=IMAGE_PNG_ASSET_URL)
        spec = _spec({"dataset": {"name": "order"}, "options": {"frames": "folders"}})
        case = DatasetImporterTestCase(importer=PixanoJsonlImporter(), source=source, spec=spec)
        dataset, _ = case.run_import(tmp_path / "data")
        frames = dataset.open_table("sequence_frames").search().select(["frame_index", "format"]).to_list()
        by_index = {row["frame_index"]: row["format"] for row in frames}
        assert by_index == {0: "PNG", 1: "JPEG"}  # name order, not pick order

    def test_folder_frames_fps_stamps_timestamps(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_frames(source / "clip", ("f0.jpg", "f1.jpg", "f2.jpg"))
        spec = _spec({"dataset": {"name": "fps"}, "options": {"frames": "folders", "fps": 10}})
        case = DatasetImporterTestCase(importer=PixanoJsonlImporter(), source=source, spec=spec)
        dataset, _ = case.run_import(tmp_path / "data")
        frames = dataset.open_table("sequence_frames").search().select(["frame_index", "timestamp"]).to_list()
        for row in frames:
            assert row["timestamp"] == pytest.approx(row["frame_index"] / 10)

    def test_invalid_fps_rejected(self, tmp_path: Path):
        from pixano.datasets.io import SpecValidationError

        source = tmp_path / "vids"
        _seed_frames(source / "clip", ("f0.jpg",))
        spec = _spec({"dataset": {"name": "bad"}, "options": {"frames": "folders", "fps": 0}})
        with pytest.raises(SpecValidationError, match="fps"):
            analyze(source, spec)

    def test_mixed_videos_and_frame_folders_error(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_frames(source / "clip", ("f0.jpg",))
        shutil.copy(VIDEO_MP4_ASSET_URL, source / "stray.mp4")
        plan = analyze(source, _spec({"dataset": {"name": "mixed"}, "options": {"frames": "folders"}}))
        assert "mixed_media_kinds" in plan.report.findings
        assert not plan.report.is_valid

    def test_images_at_split_root_error(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_images(source, ("loose",))
        plan = analyze(source, _spec({"dataset": {"name": "loose"}, "options": {"frames": "folders"}}))
        assert "frames_folder_required" in plan.report.findings
        assert not plan.report.is_valid

    def test_mixed_depth_error(self, tmp_path: Path):
        source = tmp_path / "vids"
        _seed_frames(source / "clip_a", ("f0.jpg",))
        _seed_frames(source / "front" / "clip_b", ("f0.jpg",))
        plan = analyze(source, _spec({"dataset": {"name": "depths"}, "options": {"frames": "folders"}}))
        assert "frames_depth_mismatch" in plan.report.findings
        assert not plan.report.is_valid

    def test_folders_mode_never_inferred(self, tmp_path: Path):
        """The same tree WITHOUT the option is plain multi-view images — never guessed as videos."""
        source = tmp_path / "vids"
        _seed_frames(source / "clip_a", ("f0.jpg", "f1.jpg"))
        _seed_frames(source / "clip_b", ("f0.jpg", "f1.jpg"))
        plan = analyze(source, _spec({"dataset": {"name": "plain"}}))
        assert plan.report.is_valid
        assert plan.inferred_schema["workspace"] == "image"
        assert set(plan.inferred_schema["views"]) == {"clip_a", "clip_b"}


class TestRawText:
    def test_text_folder(self, tmp_path: Path):
        source = tmp_path / "notes"
        source.mkdir()
        for stem in ("x", "y"):
            (source / f"{stem}.txt").write_text(f"hello {stem}", encoding="utf-8")
        spec = _spec({"dataset": {"name": "notes"}})
        plan = analyze(source, spec)
        assert plan.report.is_valid
        assert plan.inferred_schema["views"]["text"]["base"] == "Text"
        assert "text_span" in plan.inferred_schema and "classification" in plan.inferred_schema
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(), source=source, spec=spec, expected_counts={"records": 2, "texts": 2}
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        contents = {row.content for row in dataset.get_data("texts")}
        assert contents == {"hello x", "hello y"}

    def test_non_utf8_text_fails_analyze(self, tmp_path: Path):
        source = tmp_path / "notes"
        source.mkdir()
        (source / "ok.txt").write_text("fine", encoding="utf-8")
        (source / "bad.txt").write_bytes(b"\xff\xfe broken \xff")
        plan = analyze(source, _spec({"dataset": {"name": "notes"}}))
        assert "unreadable_text" in plan.report.findings
        assert not plan.report.is_valid

    def test_non_utf8_text_beyond_probe_budget_fails_at_ingest(self, tmp_path: Path):
        """Past the bounded analyze probes, the ingest read still fails loudly, not with a stacktrace-less row."""
        source = tmp_path / "notes"
        source.mkdir()
        for index in range(40):  # AnalyzeLimits.max_media_probes is 32
            (source / f"n{index:03d}.txt").write_text("fine", encoding="utf-8")
        (source / "z_bad.txt").write_bytes(b"\xff\xfe broken")
        spec = _spec({"dataset": {"name": "notes"}})
        plan = analyze(source, spec)
        assert plan.report.is_valid  # the bad file sorts past the probe budget
        case = DatasetImporterTestCase(importer=PixanoJsonlImporter(), source=source, spec=spec)
        with pytest.raises(MetadataError, match="not valid UTF-8"):
            case.run_import(tmp_path / "data")


class TestRequiredRecordAttrs:
    def test_required_record_attr_flagged_in_media_only_analyze(self, tmp_path: Path):
        """Media-only ingest creates records with no attr values: a required record attr can never be satisfied."""
        source = tmp_path / "raw"
        _seed_images(source, ("a",))
        spec = _spec(
            {
                "dataset": {"name": "raw", "workspace": "image"},
                "schema": {"record": {"attrs": {"weather": {"type": "str", "required": True}}}},
            }
        )
        plan = analyze(source, spec)
        assert "required_record_attr" in plan.report.findings
        assert not plan.report.is_valid

    def test_defaulted_record_attr_is_fine(self, tmp_path: Path):
        source = tmp_path / "raw"
        _seed_images(source, ("a",))
        spec = _spec(
            {"dataset": {"name": "raw", "workspace": "image"}, "schema": {"record": {"attrs": {"weather": "str"}}}}
        )
        plan = analyze(source, spec)
        assert plan.report.is_valid
        assert "required_record_attr" not in plan.report.findings


class TestInferredSchemaStamping:
    def test_user_schema_wins_over_inference(self, tmp_path: Path):
        source = tmp_path / "raw"
        _seed_images(source / "pictures", ("a",))
        spec = _spec(
            {
                "dataset": {"name": "declared", "workspace": "image"},
                "schema": {"views": {"pictures": "image"}, "annotations": ["classification"]},
            }
        )
        plan = analyze(source, spec)
        assert plan.report.is_valid
        assert set(plan.inferred_schema["views"]) == {"pictures"}
        assert "classification" in plan.inferred_schema and "bbox" not in plan.inferred_schema

    def test_jsonl_corpus_plan_carries_schema(self, tmp_path: Path):
        from tests.datasets.io.formats.test_jsonl_importer import SPECS, materialize_corpus

        source = materialize_corpus("voc_like", tmp_path)
        plan = analyze(source, ImportSpec.model_validate(SPECS["voc_like"]))
        assert plan.inferred_schema is not None
        assert plan.inferred_schema["record"]["fields"]["license"]["type"] == "str"
        assert plan.inferred_schema["entity"]["fields"]["is_difficult"]["type"] == "bool"
        assert plan.inferred_schema["views"]["image"]["base"] == "Image"


class TestEmptySourceGuard:
    def test_stray_metadata_jsonl_next_to_flat_images_is_flagged(self, tmp_path: Path):
        """A raw-image folder with a stray root metadata.jsonl must not import 0 records silently."""
        source = tmp_path / "raw"
        _seed_images(source, ("a", "b", "c"))
        (source / "metadata.jsonl").write_text('{"$pixano": "jsonl/2"}\n', encoding="utf-8")
        assert not is_media_only_source(source)  # the stray file disables media-only mode
        plan = analyze(source, _spec({"dataset": {"name": "raw", "workspace": "image"}}))
        assert plan.totals.records == 0
        assert not plan.report.is_valid
        assert "empty_source" in plan.report.findings

    def test_empty_folder_is_flagged(self, tmp_path: Path):
        source = tmp_path / "empty"
        source.mkdir()
        plan = analyze(source, _spec({"dataset": {"name": "empty", "workspace": "image"}}))
        assert not plan.report.is_valid  # no_media_found or empty_source — either way, loud

    def test_clean_flat_images_do_not_trip_the_guard(self, tmp_path: Path):
        source = tmp_path / "raw"
        _seed_images(source, ("a", "b"))
        plan = analyze(source, _spec({"dataset": {"name": "raw", "workspace": "image"}}))
        assert plan.totals.records == 2
        assert plan.report.is_valid
        assert "empty_source" not in plan.report.findings
