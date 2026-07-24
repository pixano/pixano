# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest

from pixano.datasets import DatasetInfo
from pixano.datasets.dataset_schema import _deserialize_table_schema, _serialize_table_schema
from pixano.datasets.io import ImportSpec, SchemaSpec, SpecValidationError, resolve_dataset_info, workspace_preset
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, Image, Record


def _schemas_field_identical(left: type | None, right: type | None) -> bool:
    """Field-level identity: same manifest (base + custom fields), class name aside."""
    if left is None or right is None:
        return left is right
    left_manifest = _serialize_table_schema(left)
    right_manifest = _serialize_table_schema(right)
    return (left_manifest["base"], left_manifest["fields"]) == (right_manifest["base"], right_manifest["fields"])


def _infos_field_identical(left: DatasetInfo, right: DatasetInfo) -> bool:
    if set(left.tables) != set(right.tables):
        return False
    return all(_schemas_field_identical(left.tables[name], right.tables[name]) for name in left.tables)


class TestSchemaSpecCompile:
    def test_spec_example_block_compiles(self):
        schema = SchemaSpec.model_validate(
            {
                "views": {"rgb": {"kind": "image"}, "thermal": {"kind": "image"}},
                "record": {"attrs": {"license": "str"}},
                "entity": {"attrs": {"category": "str", "is_difficult": {"type": "bool", "default": False}}},
                "annotations": ["bbox", "multi_path"],
            }
        )
        info = schema.compile(WorkspaceType.IMAGE)

        assert set(info.views) == {"rgb", "thermal"}
        assert info.views["rgb"] is info.views["thermal"]  # one class per kind (shared table)
        assert "license" in info.record.model_fields
        assert info.record.model_fields["license"].default == ""
        assert info.entity.model_fields["is_difficult"].default is False
        assert set(info.tables) == {"records", "images", "entities", "bboxes", "multi_paths"}
        assert info.keypoint is None  # the annotations list replaced the preset's slots

    def test_compiled_info_round_trips_through_info_json(self, tmp_path: Path):
        schema = SchemaSpec.model_validate({"entity": {"attrs": {"category": "str"}}, "annotations": ["bbox"]})
        info = schema.compile(WorkspaceType.IMAGE)
        info.name = "compiled"

        json_file = tmp_path / "info.json"
        info.to_json(json_file)
        loaded = DatasetInfo.from_json(json_file)

        assert "category" in loaded.entity.model_fields
        assert _infos_field_identical(info, loaded)

    def test_unknown_view_kind_and_slot(self):
        with pytest.raises(SpecValidationError, match="unknown kind 'hologram'"):
            SchemaSpec.model_validate({"views": {"x": {"kind": "hologram"}}}).compile(WorkspaceType.IMAGE)
        with pytest.raises(SpecValidationError, match="Unknown annotation slot 'hologram_box'"):
            SchemaSpec.model_validate({"annotations": ["hologram_box"]}).compile(WorkspaceType.IMAGE)

    def test_dict_typed_attr_is_out_of_dialect(self):
        with pytest.raises(SpecValidationError, match="custom Python importer"):
            SchemaSpec.model_validate({"entity": {"attrs": {"meta": {"type": "dict"}}}}).compile(WorkspaceType.IMAGE)

    def test_conflicting_attrs_on_shared_kind(self):
        schema = SchemaSpec.model_validate(
            {
                "views": {
                    "a": {"kind": "image", "attrs": {"exposure": "float"}},
                    "b": {"kind": "image", "attrs": {"gain": "float"}},
                }
            }
        )
        with pytest.raises(SpecValidationError, match="identical attrs"):
            schema.compile(WorkspaceType.IMAGE)

    def test_mel_entity_attrs_extend_the_preset_entity(self):
        """Entity attrs land on the workspace preset's entity class, not bare Entity (MEL keeps `name`)."""
        schema = SchemaSpec.model_validate({"entity": {"attrs": {"category": "str"}}})
        info = schema.compile(WorkspaceType.IMAGE_TEXT_ENTITY_LINKING)
        assert "name" in info.entity.model_fields
        assert "category" in info.entity.model_fields

    def test_collection_default_must_be_list(self):
        with pytest.raises(SpecValidationError, match="collection default must be a list"):
            SchemaSpec.model_validate(
                {"entity": {"attrs": {"tags": {"type": "str", "collection": True, "default": "foo"}}}}
            ).compile(WorkspaceType.IMAGE)

    def test_collection_list_default_compiles(self):
        info = SchemaSpec.model_validate(
            {"entity": {"attrs": {"tags": {"type": "str", "collection": True, "default": ["a"]}}}}
        ).compile(WorkspaceType.IMAGE)
        assert info.entity.model_fields["tags"].default == ["a"]

    def test_vqa_annotations_list_controls_message_slot(self):
        """A non-empty annotations list replaces the preset's slots — callers must re-list `message` to keep it."""
        keeps = SchemaSpec.model_validate({"annotations": ["message"]}).compile(WorkspaceType.IMAGE_VQA)
        assert keeps.message is not None
        drops = SchemaSpec.model_validate({"annotations": ["bbox"]}).compile(WorkspaceType.IMAGE_VQA)
        assert drops.message is None


class TestFromDatasetInfoInverse:
    @pytest.mark.parametrize(
        "workspace",
        [
            WorkspaceType.IMAGE,
            WorkspaceType.VIDEO,
            WorkspaceType.IMAGE_VQA,
            WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
        ],
    )
    def test_identity_on_workspace_presets(self, workspace):
        info = workspace_preset(workspace)
        recompiled = SchemaSpec.from_dataset_info(info).compile(workspace)
        assert _infos_field_identical(info, recompiled)

    def test_identity_with_custom_attrs(self):
        original = SchemaSpec.model_validate(
            {
                "views": {"image": {"kind": "image"}},
                "record": {"attrs": {"license": "str"}},
                "entity": {"attrs": {"category": "str", "score": {"type": "float", "required": True}}},
                "annotations": {"bbox": {"attrs": {"quality": "float"}}},
            }
        ).compile(WorkspaceType.IMAGE)

        recompiled = SchemaSpec.from_dataset_info(original).compile(WorkspaceType.IMAGE)
        assert _infos_field_identical(original, recompiled)


class TestSchemaManifestPassthrough:
    def test_exotic_info_round_trips_verbatim(self):
        # A schema outside the authoring dialect (subclass with a custom name) passes
        # through schema_manifest untouched.
        original = DatasetInfo(
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=type("ExoticEntity", (Entity,), {"__annotations__": {"wingspan": float}, "wingspan": 0.0}),
            bbox=BBox,
            views={"image": Image},
        )
        manifest = {
            "record": _serialize_table_schema(original.record),
            "entity": _serialize_table_schema(original.entity),
            "bbox": _serialize_table_schema(original.bbox),
            "views": {"image": _serialize_table_schema(Image)},
        }
        spec = ImportSpec.model_validate({"dataset": {"workspace": "image"}, "schema_manifest": manifest})
        resolved = resolve_dataset_info(spec)

        assert _infos_field_identical(original, resolved)
        assert resolved.entity.__name__ == "ExoticEntity"  # verbatim, name preserved

    def test_shorthand_beats_preset_and_manifest_beats_shorthand(self):
        spec = ImportSpec.model_validate({"dataset": {"workspace": "image"}, "schema": {"annotations": ["mask"]}})
        assert set(resolve_dataset_info(spec).tables) == {"records", "images", "entities", "masks"}

        preset_only = ImportSpec.model_validate({"dataset": {"workspace": "image"}})
        assert "keypoints" in resolve_dataset_info(preset_only).tables


class TestSerializerHardError:
    def test_nameless_fields_manifest_raises(self):
        with pytest.raises(ValueError, match="refusing to silently drop"):
            _deserialize_table_schema(
                {"base": "Entity", "fields": {"category": {"type": "str", "collection": False, "required": False}}}
            )

    def test_nameless_empty_fields_still_returns_base(self):
        assert _deserialize_table_schema({"base": "Entity", "fields": {}}) is Entity


class TestSpecExampleYamlStillValid:
    def test_full_yaml_with_schema_compiles(self, tmp_path: Path):
        spec_file = tmp_path / "dataset.yaml"
        spec_file.write_text(
            """
pixano: 2
dataset:
  name: "FLIR ADAS"
  workspace: image
format: pixano_jsonl
schema:
  views:
    rgb: {kind: image}
    thermal: {kind: image}
  entity:
    attrs: {category: str}
  annotations: [bbox]
"""
        )
        spec = ImportSpec.from_yaml(spec_file)
        info = resolve_dataset_info(spec)
        assert set(info.views) == {"rgb", "thermal"}
        assert "category" in info.entity.model_fields
