# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

import pytest

from pixano.datasets.io import PreflightReport
from pixano.datasets.io.formats.pixano_jsonl import parse_file, view_kinds_of
from pixano.datasets.io.formats.pixano_jsonl.spec import SequenceFramesPayload, TextViewPayload, VideoViewPayload
from pixano.datasets.io.spec import SchemaSpec, workspace_preset
from pixano.datasets.workspaces import WorkspaceType


CORPUS_ROOT = Path(__file__).parents[3] / "assets" / "jsonl_v2"

# Declared view kinds per corpus (what the dataset.yaml schema block would say).
CORPUS_VIEWS: dict[str, dict[str, str]] = {
    "voc_like": {"image": "image"},
    "multiview": {"rgb": "image", "thermal": "image"},
    "video_track": {"camera": "video"},
    "frames_masks": {"camera": "sequence_frames"},
    "vqa": {"image": "image"},
    "mel": {"image": "image", "text": "text"},
    "lerobot_window": {"cam_top": "video", "cam_wrist": "video"},
    "mixed_media": {"image": "image", "clip": "video"},
}


def _parse_corpus(name: str) -> tuple[list, PreflightReport]:
    report = PreflightReport()
    path = CORPUS_ROOT / name / "train" / "metadata.jsonl"
    lines = list(parse_file(path, "train", CORPUS_VIEWS[name], report))
    return lines, report


class TestGoldenCorpora:
    @pytest.mark.parametrize("name", sorted(CORPUS_VIEWS))
    def test_corpus_parses_without_findings(self, name: str):
        lines, report = _parse_corpus(name)
        assert report.error_count == 0, {code: f.suggestion for code, f in report.findings.items()}
        assert len(lines) >= 1

    def test_voc_like_semantics(self):
        lines, _ = _parse_corpus("voc_like")
        line = lines[0]
        assert line.model.id == "voc_000042"
        assert line.split == "train"
        assert line.defaults.bbox.format == "xywh"  # header defaults captured
        assert line.defaults.source.name == "voc2007"
        annotations = line.model.entities[0].annotations
        assert [a.kind for a in annotations] == ["bbox", "keypoints", "mask"]
        assert annotations[2].polygons is not None

    def test_video_window_payload(self):
        lines, _ = _parse_corpus("video_track")
        camera = lines[0].views["camera"]
        assert isinstance(camera, VideoViewPayload)
        assert camera.fps == 24
        assert camera.to_timestamp == -1.0
        entity = lines[0].model.entities[0]
        assert entity.tracklets[0].end_timestep == 81
        assert entity.states[0].attrs == {"occluded": True}

    def test_sequence_pattern_and_sidecar(self):
        lines, _ = _parse_corpus("frames_masks")
        camera = lines[0].views["camera"]
        assert isinstance(camera, SequenceFramesPayload)
        assert camera.frame_pattern == "frames/bear/*.jpg"
        sidecar = lines[0].model.annotation_files[0]
        assert (sidecar.kind, sidecar.encoding, sidecar.entity_map) == ("mask", "index_png", "auto")

    def test_mel_inline_text(self):
        lines, _ = _parse_corpus("mel")
        text = lines[0].views["text"]
        assert isinstance(text, TextViewPayload)
        assert text.content is not None and text.uri is None

    def test_lerobot_window_line(self):
        lines, _ = _parse_corpus("lerobot_window")
        cam_top = lines[0].views["cam_top"]
        assert cam_top.from_timestamp == 68.27
        assert cam_top.to_timestamp == 82.0


def _report_for(line: dict, views: dict[str, str] | None = None, tmp_path: Path | None = None) -> PreflightReport:
    path = tmp_path / "metadata.jsonl"
    path.write_text(json.dumps(line) + "\n")
    report = PreflightReport()
    list(parse_file(path, "train", views or {"image": "image"}, report))
    return report


class TestMutationSuite:
    def test_unknown_top_level_key_with_suggestion(self, tmp_path: Path):
        report = _report_for({"views": {"image": "a.jpg"}, "entitees": []}, tmp_path=tmp_path)
        finding = report.findings["unknown_key"]
        assert finding.severity == "error"
        assert "entities" in finding.suggestion  # did-you-mean
        assert finding.samples[0].line == 1

    def test_v1_dialect_points_at_migrate_jsonl(self, tmp_path: Path):
        v1_line = {"status": "validated", "views": {"image": "a.jpg"}, "objects": []}
        report = _report_for(v1_line, tmp_path=tmp_path)
        assert "v1_format" in report.findings
        assert "migrate-jsonl" in report.findings["v1_format"].suggestion

    def test_unknown_annotation_kind(self, tmp_path: Path):
        line = {"views": {"image": "a.jpg"}, "entities": [{"annotations": [{"kind": "boxx", "coords": [0, 0, 1, 1]}]}]}
        report = _report_for(line, tmp_path=tmp_path)
        assert "unknown_kind" in report.findings
        assert "bbox" in report.findings["unknown_kind"].suggestion

    def test_reserved_3d_kind(self, tmp_path: Path):
        line = {"views": {"image": "a.jpg"}, "entities": [{"annotations": [{"kind": "bbox3d"}]}]}
        report = _report_for(line, tmp_path=tmp_path)
        assert "reserved_kind" in report.findings

    def test_undeclared_view_with_suggestion(self, tmp_path: Path):
        report = _report_for({"views": {"imge": "a.jpg"}}, tmp_path=tmp_path)
        assert "undeclared_view" in report.findings
        assert "image" in report.findings["undeclared_view"].suggestion

    def test_bbox_without_format_or_defaults(self, tmp_path: Path):
        line = {
            "views": {"image": "a.jpg"},
            "entities": [{"annotations": [{"kind": "bbox", "coords": [0.1, 0.1, 0.2, 0.2]}]}],
        }
        report = _report_for(line, tmp_path=tmp_path)
        assert "bbox_defaults_required" in report.findings  # never [0,1]-sniffed

    def test_view_required_on_multi_view(self, tmp_path: Path):
        line = {
            "views": {"rgb": "a.jpg", "thermal": "b.jpg"},
            "entities": [
                {
                    "annotations": [
                        {"kind": "bbox", "coords": [0.1, 0.1, 0.2, 0.2], "format": "xywh", "is_normalized": True}
                    ]
                }
            ],
        }
        report = _report_for(line, views={"rgb": "image", "thermal": "image"}, tmp_path=tmp_path)
        assert "view_required" in report.findings

    def test_question_without_question_type(self, tmp_path: Path):
        line = {
            "views": {"image": "a.jpg"},
            "conversations": [{"messages": [{"type": "QUESTION", "content": "?"}]}],
        }
        report = _report_for(line, tmp_path=tmp_path)
        assert "question_type_required" in report.findings

    def test_invalid_json_line(self, tmp_path: Path):
        path = tmp_path / "metadata.jsonl"
        path.write_text('{"views": {"image": "a.jpg"}\n')  # unclosed
        report = PreflightReport()
        assert list(parse_file(path, "train", {"image": "image"}, report)) == []
        assert "invalid_json" in report.findings

    def test_header_after_first_line_rejected(self, tmp_path: Path):
        path = tmp_path / "metadata.jsonl"
        path.write_text('{"views": {"image": "a.jpg"}}\n{"$pixano": "jsonl/2"}\n')
        report = PreflightReport()
        lines = list(parse_file(path, "train", {"image": "image"}, report))
        assert len(lines) == 1
        assert "header_not_first" in report.findings

    def test_text_uri_xor_content(self, tmp_path: Path):
        line = {"views": {"doc": {"uri": "a.txt", "content": "inline"}}}
        report = _report_for(line, views={"doc": "text"}, tmp_path=tmp_path)
        assert report.error_count > 0

    def test_max_lines_bound(self, tmp_path: Path):
        path = tmp_path / "metadata.jsonl"
        path.write_text("\n".join(json.dumps({"views": {"image": f"{n}.jpg"}}) for n in range(50)) + "\n")
        report = PreflightReport()
        lines = list(parse_file(path, "train", {"image": "image"}, report, max_lines=10))
        assert len(lines) == 10


class TestViewKindsOf:
    def test_kinds_from_compiled_schema(self):
        info = SchemaSpec.model_validate({"views": {"rgb": {"kind": "image"}, "clip": {"kind": "video"}}}).compile(
            WorkspaceType.IMAGE
        )
        assert view_kinds_of(info) == {"rgb": "image", "clip": "video"}

    def test_kinds_from_preset(self):
        assert view_kinds_of(workspace_preset(WorkspaceType.IMAGE_TEXT_ENTITY_LINKING)) == {
            "image": "image",
            "text": "text",
        }
