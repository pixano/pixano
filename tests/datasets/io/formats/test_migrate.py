# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest

from pixano.datasets.io import PreflightReport
from pixano.datasets.io.formats.pixano_jsonl import parse_file
from pixano.datasets.io.formats.pixano_jsonl.migrate import migrate_tree


V1_ROOT = Path(__file__).parents[3] / "assets" / "jsonl_v1"

# Declared view kinds each migrated corpus should be parsed against.
V1_VIEWS: dict[str, dict[str, str]] = {
    "canonical": {"image": "image"},
    "aliases": {"image": "image"},
    "video": {"image": "sequence_frames"},
    "vqa": {"image": "image"},
    "ambiguous": {"image": "image", "text": "text"},
}


class TestMigrateCorpus:
    @pytest.mark.parametrize("name", sorted(V1_VIEWS))
    def test_migrated_output_passes_the_v2_parser(self, name: str, tmp_path: Path):
        report = migrate_tree(V1_ROOT / name, tmp_path / name)

        parser_report = PreflightReport()
        lines = list(parse_file(tmp_path / name / "train" / "metadata.jsonl", "train", V1_VIEWS[name], parser_report))
        assert parser_report.error_count == 0, {
            code: finding.suggestion for code, finding in parser_report.findings.items()
        }
        assert len(lines) == report.lines_migrated == 1

    def test_alias_spellings_are_normalized(self, tmp_path: Path):
        migrate_tree(V1_ROOT / "aliases", tmp_path)
        parser_report = PreflightReport()
        (line,) = parse_file(tmp_path / "train" / "metadata.jsonl", "train", {"image": "image"}, parser_report)
        assert "image" in line.views  # bare 'image' key -> views
        annotation = line.model.entities[0].annotations[0]
        assert annotation.kind == "bbox"
        assert annotation.is_normalized is False  # 10 > 1: pixel coords detected

    def test_video_globs_become_frame_patterns_and_sidecars(self, tmp_path: Path):
        migrate_tree(V1_ROOT / "video", tmp_path)
        parser_report = PreflightReport()
        (line,) = parse_file(
            tmp_path / "train" / "metadata.jsonl", "train", {"image": "sequence_frames"}, parser_report
        )
        assert line.views["image"].frame_pattern == "frames/bear/*.jpg"
        assert line.views["image"].fps == 24
        assert line.model.annotation_files[0].encoding == "index_png"

    def test_vqa_nested_messages_become_conversations(self, tmp_path: Path):
        migrate_tree(V1_ROOT / "vqa", tmp_path)
        parser_report = PreflightReport()
        (line,) = parse_file(tmp_path / "train" / "metadata.jsonl", "train", {"image": "image"}, parser_report)
        messages = line.model.conversations[0].messages
        assert [m.type for m in messages] == ["QUESTION", "ANSWER"]
        assert messages[0].question_type == "OPEN"  # lowercase v1 value uppercased

    def test_ambiguous_span_is_flagged(self, tmp_path: Path):
        report = migrate_tree(V1_ROOT / "ambiguous", tmp_path)
        assert any("mention" in note for note in report.needs_attention)
        # Inline v1 text views were paths-or-inline ambiguity; migrated as string views the
        # v2 parser then validates against the declared 'text' kind.
