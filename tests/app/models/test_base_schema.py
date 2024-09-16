# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.app.models import BaseSchemaModel, TableInfo
from pixano.features import Item


class TestBaseModelSchema:
    def test_init(self):
        id = "id"
        table_info = TableInfo(name="table", group="views", base_schema="Image")
        data = {}
        BaseSchemaModel(id=id, table_info=table_info, data=data)

    def test_from_row(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        item = Item(id="id", split="train")
        model = BaseSchemaModel.from_row(item, table_info)

        assert model == BaseSchemaModel(id="id", table_info=table_info, data={"split": "train"})

    def test_from_rows(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        items = [Item(id="id1", split="train"), Item(id="id2", split="test")]
        models = BaseSchemaModel.from_rows(items, table_info)

        assert models == [
            BaseSchemaModel(id="id1", table_info=table_info, data={"split": "train"}),
            BaseSchemaModel(id="id2", table_info=table_info, data={"split": "test"}),
        ]

    def test_to_row(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        model = BaseSchemaModel(id="id", table_info=table_info, data={"split": "train"})
        item = model.to_row(Item)

        assert item == Item(id="id", split="train")

    def test_to_rows(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        models = [
            BaseSchemaModel(id="id1", table_info=table_info, data={"split": "train"}),
            BaseSchemaModel(id="id2", table_info=table_info, data={"split": "test"}),
        ]
        items = BaseSchemaModel.to_rows(models, Item)

        assert items == [
            Item(id="id1", split="train"),
            Item(id="id2", split="test"),
        ]
