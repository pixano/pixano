# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import create_model

from pixano.schemas import Entity, label_field_of


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
