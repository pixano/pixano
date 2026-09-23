# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path

from pydantic import create_model

from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import BBox, Entity, Image, Record, label_field_of


def _dataset(entity: type[Entity]) -> Dataset:
    target = Path(tempfile.mkdtemp()) / "ds"
    dataset = Dataset.create(
        target, DatasetInfo(name="ds", record=Record, entity=entity, views={"image": Image}, bbox=BBox)
    )
    dataset.add_records({"records": [Record(id="r1")]})
    dataset.add_data("entities", [entity(id="e1", record_id="r1")], raise_or_warn="none")
    return dataset


class TestLabelFieldOf:
    """The field that names what an entity is — the interface reads it with the same rule."""

    def test_a_known_label_field_comes_first(self) -> None:
        schema = create_model("E", __base__=Entity, color=(str, ""), category=(str, ""))
        assert label_field_of(schema) == "category"

    def test_else_the_first_text_field(self) -> None:
        schema = create_model("E", __base__=Entity, count=(int, 0), color=(str, ""))
        assert label_field_of(schema) == "color"

    def test_none_when_entities_hold_no_text(self) -> None:
        """nuScenes as imported, a dataset of plain images."""
        assert label_field_of(Entity) is None


class TestEnsureEntityTextField:
    """Step 2, lot 2: a detection job writes a class; a dataset without a field to hold it gets one."""

    def test_adds_the_field_to_the_schema_the_table_and_info_json(self) -> None:
        dataset = _dataset(Entity)

        dataset.ensure_entity_text_field("category")

        assert "category" in dataset.open_table("entities").schema.names
        assert label_field_of(dataset.info.entity) == "category"
        reopened = Dataset(dataset.path)
        assert label_field_of(reopened.info.entity) == "category"
        assert [entity.category for entity in reopened.get_data("entities")] == [""]

    def test_an_entity_with_a_class_can_be_written_afterwards(self) -> None:
        dataset = _dataset(Entity)
        dataset.ensure_entity_text_field("category")

        dataset.add_data(
            "entities", [dataset.info.entity(id="e2", record_id="r1", category="cat")], raise_or_warn="none"
        )

        classes = {entity.id: entity.category for entity in Dataset(dataset.path).get_data("entities")}
        assert classes == {"e1": "", "e2": "cat"}

    def test_is_idempotent_and_keeps_an_existing_field(self) -> None:
        schema = create_model("VocEntity", __base__=Entity, category=(str, ""))
        dataset = _dataset(schema)

        dataset.ensure_entity_text_field("category")
        dataset.ensure_entity_text_field("category")

        assert dataset.open_table("entities").schema.names.count("category") == 1
        assert Dataset(dataset.path).info.entity.__name__ == "VocEntity"
