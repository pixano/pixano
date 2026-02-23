# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

from pixano.datasets.dataset_schema import DatasetItem, SchemaRelation, _columns_to_view_dict, _view_instance_to_columns
from pixano.features.schemas import BBox, Entity, Image, SequenceFrame


class SceneItem(DatasetItem):
    rgb: Image
    cam_front: list[SequenceFrame]
    objects: list[Entity]
    bboxes: list[BBox]
    location: str


def test_schema_v2_from_dataset_item_media_tables_are_narrow():
    schema = SceneItem.to_dataset_schema()

    assert set(schema.schemas) == {"item", "images", "frames", "objects", "bboxes"}
    assert schema.relations["item"]["images"] == SchemaRelation.ONE_TO_ONE
    assert schema.relations["item"]["frames"] == SchemaRelation.ONE_TO_MANY

    assert schema.view_columns["rgb"].media_table == "images"
    assert schema.view_columns["rgb"].is_collection is False
    assert schema.view_columns["cam_front"].media_table == "frames"
    assert schema.view_columns["cam_front"].is_collection is True

    assert "view_name" in schema.schemas["images"].model_fields
    assert "item_id" in schema.schemas["images"].model_fields
    assert "view_name" in schema.schemas["frames"].model_fields
    assert "frame_index" in schema.schemas["frames"].model_fields


def test_view_row_conversion_helpers_for_narrow_layout():
    frame = SequenceFrame(
        id="f1",
        item_id="item_1",
        view_name="cam_front",
        url="frame_0001.png",
        width=640,
        height=480,
        format="png",
        blob=b"",
        frame_index=1,
        timestamp=0.1,
    )

    row = _view_instance_to_columns("cam_front", frame)
    assert row["item_id"] == "item_1"
    assert row["view_name"] == "cam_front"
    assert row["frame_index"] == 1

    same_view = _columns_to_view_dict("cam_front", row)
    assert same_view["id"] == "f1"

    other_view = _columns_to_view_dict("cam_rear", row)
    assert other_view == {}


def test_dataset_item_model_uses_per_view_cardinality():
    schema = SceneItem.to_dataset_schema()
    item_model = DatasetItem.from_dataset_schema(schema)

    rgb_field = item_model.model_fields["rgb"]
    cam_front_field = item_model.model_fields["cam_front"]

    assert "Image" in str(rgb_field.annotation)
    assert "list" in str(cam_front_field.annotation)
    assert "SequenceFrame" in str(cam_front_field.annotation)

