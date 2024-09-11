# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import ItemModel, TableInfo
from pixano.features import Entity, Item


class TestItemModel:
    def test_to_row(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        model = ItemModel(
            id="id",
            table_info=table_info,
            data={
                "split": "default",
            },
        )
        item = model.to_row(Item)

        assert item == Item(
            id="id",
        )

        with pytest.raises(ValueError, match="Schema type must be a subclass of Item."):
            model.to_row(Entity)

        table_info = TableInfo(name="item", group="views", base_schema="Item")
        with pytest.raises(ValueError, match="Table info group must be item."):
            model.table_info = table_info
