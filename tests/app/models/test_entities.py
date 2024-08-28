# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import EntityModel, TableInfo
from pixano.features import Entity, Item


class TestEntityModel:
    def test_to_row(self):
        table_info = TableInfo(name="entity", group="entities", base_schema="Entity")
        model = EntityModel(
            id="id",
            table_info=table_info,
            data={
                "item_ref": {"id": "", "name": ""},
                "view_ref": {"id": "", "name": ""},
                "parent_ref": {"id": "", "name": ""},
            },
        )
        entity = model.to_row(Entity)

        assert entity == Entity(
            id="id",
            item_ref={"id": "", "name": ""},
            view_ref={"id": "", "name": ""},
            parent_ref={"id": "", "name": ""},
        )

        with pytest.raises(ValueError, match="Schema type must be a subclass of Entity."):
            model.to_row(Item)
