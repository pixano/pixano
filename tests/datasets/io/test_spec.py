# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest

from pixano.datasets.io import ImportSpec, SpecValidationError, workspace_preset
from pixano.datasets.io.spec import MelEntity
from pixano.datasets.workspaces import WorkspaceType


EXAMPLE_YAML = """
pixano: 2
dataset:
  name: "FLIR ADAS"
  description: "RGB + thermal detection"
  workspace: image
format: pixano_jsonl
media:
  mode: embed
schema:
  views:
    rgb: {kind: image}
    thermal: {kind: image}
  record:
    attrs: {license: str}
  entity:
    attrs: {category: str}
  annotations: [bbox, multi_path]
defaults:
  source: {type: ground_truth, name: flir_adas_v2}
ids:
  policy: derive
  namespace: flir_adas_v2
mode: create
options: {}
"""


class TestImportSpec:
    def test_yaml_equals_kwargs(self, tmp_path: Path):
        spec_file = tmp_path / "pixano.yaml"
        spec_file.write_text(EXAMPLE_YAML)
        from_yaml = ImportSpec.from_yaml(spec_file)

        from_kwargs = ImportSpec.model_validate(
            {
                "dataset": {"name": "FLIR ADAS", "description": "RGB + thermal detection", "workspace": "image"},
                "format": "pixano_jsonl",
                "media": {"mode": "embed"},
                "schema": {
                    "views": {"rgb": {"kind": "image"}, "thermal": {"kind": "image"}},
                    "record": {"attrs": {"license": "str"}},
                    "entity": {"attrs": {"category": "str"}},
                    "annotations": ["bbox", "multi_path"],
                },
                "defaults": {"source": {"type": "ground_truth", "name": "flir_adas_v2"}},
                "ids": {"policy": "derive", "namespace": "flir_adas_v2"},
                "mode": "create",
            }
        )
        assert from_yaml == from_kwargs
        assert from_yaml.fingerprint() == from_kwargs.fingerprint()

    def test_defaults(self):
        spec = ImportSpec()
        assert spec.media.mode == "embed"  # embed is the product default (spec §6)
        assert spec.ids.policy == "derive"
        assert spec.mode == "create"
        assert spec.format == "auto"

    def test_unknown_keys_rejected(self, tmp_path: Path):
        spec_file = tmp_path / "pixano.yaml"
        spec_file.write_text("pixano: 2\nmedia_root: /somewhere\n")
        with pytest.raises(SpecValidationError, match="media_root"):
            ImportSpec.from_yaml(spec_file)

    def test_invalid_yaml_carries_file_provenance(self, tmp_path: Path):
        spec_file = tmp_path / "pixano.yaml"
        spec_file.write_text("pixano: [unclosed")
        with pytest.raises(SpecValidationError, match=str(spec_file)):
            ImportSpec.from_yaml(spec_file)

    def test_fingerprint_changes_with_content(self):
        base = ImportSpec()
        other = ImportSpec.model_validate({"mode": "add"})
        assert base.fingerprint() != other.fingerprint()


class TestWorkspacePresets:
    @pytest.mark.parametrize(
        "workspace,expected_tables",
        [
            (WorkspaceType.IMAGE, {"records", "images", "entities", "bboxes", "keypoints"}),
            (
                WorkspaceType.VIDEO,
                {
                    "records",
                    "sequence_frames",
                    "entities",
                    "entity_dynamic_states",
                    "bboxes",
                    "keypoints",
                    "tracklets",
                },
            ),
            (WorkspaceType.IMAGE_VQA, {"records", "images", "entities", "messages"}),
            (
                WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
                {"records", "images", "texts", "entities", "text_spans", "bboxes", "masks"},
            ),
        ],
    )
    def test_presets_match_v1_builder_defaults(self, workspace, expected_tables):
        info = workspace_preset(workspace)
        assert set(info.tables) == expected_tables
        assert info.workspace == workspace

    def test_presets_are_fresh_instances(self):
        first = workspace_preset(WorkspaceType.IMAGE)
        second = workspace_preset(WorkspaceType.IMAGE)
        assert first is not second

    def test_mel_entity_has_name_field(self):
        info = workspace_preset(WorkspaceType.IMAGE_TEXT_ENTITY_LINKING)
        assert info.entity is MelEntity
        assert "name" in MelEntity.model_fields

    def test_undefined_workspace_has_no_preset(self):
        with pytest.raises(SpecValidationError, match="No workspace preset"):
            workspace_preset(WorkspaceType.UNDEFINED)
