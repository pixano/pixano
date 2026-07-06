# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shutil
from pathlib import Path

import numpy as np
import PIL.Image
import pytest

from pixano.datasets.io import FORMATS, ImportSpec, SourceRef, ffprobe_available
from pixano.datasets.io.formats.pixano_jsonl import PixanoJsonlImporter
from pixano.datasets.io.ids import namespace_prefix
from pixano.datasets.io.testing import DatasetImporterTestCase
from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL, IMAGE_PNG_ASSET_URL, VIDEO_MP4_ASSET_URL


CORPUS_ROOT = Path(__file__).parents[3] / "assets" / "jsonl_v2"

# Media each corpus references, materialized from the sample assets at test time.
MEDIA: dict[str, dict[str, Path]] = {
    "voc_like": {"train/JPEGImages/000042.jpg": IMAGE_JPG_ASSET_URL},
    "multiview": {"train/rgb/000001.jpg": IMAGE_JPG_ASSET_URL, "train/thermal/000001.jpg": IMAGE_PNG_ASSET_URL},
    "video_track": {"train/videos/bear.mp4": VIDEO_MP4_ASSET_URL},
    "vqa": {"train/000001.jpg": IMAGE_JPG_ASSET_URL},
    "mel": {"train/images/eiffel.jpg": IMAGE_JPG_ASSET_URL},
    "frames_masks": {},
    "lerobot_window": {},
    "mixed_media": {"train/photo.jpg": IMAGE_JPG_ASSET_URL},
}

SPECS: dict[str, dict] = {
    "voc_like": {
        "dataset": {"name": "voc_like", "workspace": "image"},
        "schema": {
            "record": {"attrs": {"license": "str"}},
            "entity": {"attrs": {"category": "str", "is_difficult": {"type": "bool", "default": False}}},
            "annotations": ["bbox", "keypoint", "mask"],
        },
    },
    "multiview": {
        "dataset": {"name": "multiview", "workspace": "image"},
        "schema": {
            "views": {"rgb": {"kind": "image"}, "thermal": {"kind": "image"}},
            "entity": {"attrs": {"category": "str"}},
            "annotations": ["bbox", "multi_path"],
        },
    },
    "video_track": {
        "dataset": {"name": "video_track", "workspace": "video"},
        "schema": {
            "views": {"camera": {"kind": "video"}},
            "entity": {"attrs": {"category": "str"}},
            "entity_dynamic_state": {"attrs": {"occluded": {"type": "bool", "default": False}}},
            "annotations": ["bbox", "tracklet"],
        },
    },
    "frames_masks": {
        "dataset": {"name": "frames_masks", "workspace": "video"},
        "schema": {
            "views": {"camera": {"kind": "sequence_frames"}},
            "annotations": ["mask", "tracklet"],
        },
    },
    "vqa": {
        "dataset": {"name": "vqa", "workspace": "image_vqa"},
        "schema": {"annotations": ["message"]},
    },
    "mel": {
        "dataset": {"name": "mel", "workspace": "image_text_entity_linking"},
        "schema": {
            "views": {"image": {"kind": "image"}, "text": {"kind": "text"}},
            "entity": {"attrs": {"name": "str"}},
            "annotations": ["bbox", "text_span"],
        },
    },
    "lerobot_window": {
        "dataset": {"name": "lerobot_window", "workspace": "video"},
        "schema": {
            "views": {"cam_top": {"kind": "video"}, "cam_wrist": {"kind": "video"}},
            "record": {
                "attrs": {
                    "episode_index": "int",
                    "tasks": {"type": "str", "collection": True},
                    "length": "int",
                }
            },
            "annotations": ["bbox"],
        },
    },
    "mixed_media": {
        "dataset": {"name": "mixed_media", "workspace": "image"},
        "schema": {
            "views": {"image": {"kind": "image"}, "clip": {"kind": "video"}},
            "entity": {"attrs": {"category": "str"}},
            "annotations": ["classification"],
        },
    },
}

EXPECTED_COUNTS: dict[str, dict[str, int]] = {
    "voc_like": {"records": 1, "images": 1, "entities": 1, "bboxes": 1, "keypoints": 1, "masks": 1},
    "multiview": {"records": 1, "images": 2, "entities": 1, "bboxes": 1, "multi_paths": 1},
    "video_track": {"records": 1, "videos": 1, "entities": 1, "tracklets": 1, "entity_dynamic_states": 1, "bboxes": 2},
    "frames_masks": {"records": 1, "sequence_frames": 2, "entities": 2, "masks": 3, "tracklets": 2},
    "vqa": {"records": 1, "images": 1, "messages": 2},
    "mel": {"records": 1, "images": 1, "texts": 1, "entities": 1, "bboxes": 1, "text_spans": 1},
    "lerobot_window": {"records": 1, "videos": 2},
    "mixed_media": {"records": 1, "images": 1, "videos": 1, "entities": 1, "classifications": 1},
}

EXPECTED_STORAGE: dict[str, str] = {
    "voc_like": "embedded",
    "multiview": "embedded",
    "video_track": "embedded",
    "frames_masks": "embedded",
    "vqa": "embedded",
    "mel": "embedded",
    "lerobot_window": "filesystem",
    "mixed_media": "mixed",
}

NEEDS_FFPROBE = {"video_track"}


def materialize_corpus(name: str, tmp_path: Path) -> Path:
    """Copy a golden corpus and its media into a temp source directory."""
    source_dir = tmp_path / name
    shutil.copytree(CORPUS_ROOT / name, source_dir)
    for relative, asset in MEDIA[name].items():
        target = source_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(asset, target)
    if name == "frames_masks":
        frames_dir = source_dir / "train" / "frames" / "bear"
        masks_dir = source_dir / "train" / "masks" / "bear"
        frames_dir.mkdir(parents=True)
        masks_dir.mkdir(parents=True)
        for frame_index, values in enumerate([{1}, {1, 2}]):
            shutil.copy(IMAGE_JPG_ASSET_URL, frames_dir / f"{frame_index:05d}.jpg")
            mask = np.zeros((8, 8), dtype=np.uint8)
            for value in values:
                mask[value, :] = value
            PIL.Image.fromarray(mask).save(masks_dir / f"{frame_index:05d}.png")
    return source_dir


def _case(name: str, tmp_path: Path) -> DatasetImporterTestCase:
    return DatasetImporterTestCase(
        importer=PixanoJsonlImporter(),
        source=materialize_corpus(name, tmp_path),
        spec=ImportSpec.model_validate({**SPECS[name], "ids": {"namespace": name}}),
        expected_counts=EXPECTED_COUNTS[name],
    )


class TestGoldenCorporaImport:
    @pytest.mark.parametrize("name", sorted(SPECS))
    def test_corpus_end_to_end(self, name: str, tmp_path: Path):
        if name in NEEDS_FFPROBE and not ffprobe_available():
            pytest.skip("ffprobe not installed")
        case = _case(name, tmp_path / "src")
        case.assert_analyze_clean()
        dataset, result = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_storage_mode(dataset, EXPECTED_STORAGE[name])
        case.assert_idempotent_rerun(dataset, tmp_path / "data")

    def test_derived_ids_carry_namespace(self, tmp_path: Path):
        case = _case("multiview", tmp_path / "src")
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_id_prefix(dataset, namespace_prefix("multiview"))

    def test_video_window_row(self, tmp_path: Path):
        case = _case("lerobot_window", tmp_path / "src")
        dataset, _ = case.run_import(tmp_path / "data")
        videos = sorted(dataset.get_data("videos"), key=lambda v: v.logical_name)
        assert [v.logical_name for v in videos] == ["cam_top", "cam_wrist"]
        assert videos[0].from_timestamp == 68.27
        assert videos[0].to_timestamp == 82.0
        assert videos[0].num_frames == round((82.0 - 68.27) * 30)
        assert videos[0].uri.startswith("https://huggingface.co/")

    def test_explicit_id_is_preserved(self, tmp_path: Path):
        case = _case("voc_like", tmp_path / "src")
        dataset, _ = case.run_import(tmp_path / "data")
        assert dataset.get_data("records")[0].id == "voc_000042"
        assert dataset.get_data("records")[0].license == "voc2007"

    def test_vqa_message_numbering(self, tmp_path: Path):
        case = _case("vqa", tmp_path / "src")
        dataset, _ = case.run_import(tmp_path / "data")
        messages = sorted(dataset.get_data("messages"), key=lambda m: m.type)
        answer, question = messages
        assert question.number == 0 and answer.number == 0
        assert question.question_type == "SINGLE_CHOICE"
        assert question.conversation_id == answer.conversation_id

    def test_sidecar_masks_and_tracklets(self, tmp_path: Path):
        case = _case("frames_masks", tmp_path / "src")
        dataset, _ = case.run_import(tmp_path / "data")
        tracklets = {t.entity_id: (t.start_timestep, t.end_timestep) for t in dataset.get_data("tracklets")}
        entities = dataset.get_data("entities")
        assert len(entities) == 2
        spans = sorted(tracklets.values())
        assert spans == [(0, 1), (1, 1)]  # object 1 in both frames, object 2 only in frame 1

    def test_detection(self, tmp_path: Path):
        source_dir = materialize_corpus("voc_like", tmp_path)
        detected = FORMATS.detect(SourceRef.from_string(str(source_dir)))
        assert detected.name == "pixano_jsonl"

    def test_media_only_mode(self, tmp_path: Path):
        source_dir = tmp_path / "raw"
        (source_dir / "train").mkdir(parents=True)
        for stem in ("a", "b", "c"):
            shutil.copy(IMAGE_JPG_ASSET_URL, source_dir / "train" / f"{stem}.jpg")
        spec = ImportSpec.model_validate({"dataset": {"name": "raw_images", "workspace": "image"}})
        case = DatasetImporterTestCase(
            importer=PixanoJsonlImporter(),
            source=source_dir,
            spec=spec,
            expected_counts={"records": 3, "images": 3},
        )
        dataset, _ = case.run_import(tmp_path / "data")
        case.assert_counts(dataset)
        case.assert_storage_mode(dataset, "embedded")
