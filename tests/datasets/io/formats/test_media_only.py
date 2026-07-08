# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shutil
from pathlib import Path

import pytest

from pixano.datasets.io import FORMATS, ImportSpec, SourceRef, analyze, ffmpeg_available, ffprobe_available
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
