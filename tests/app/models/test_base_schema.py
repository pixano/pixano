# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.app.models import BaseModelSchema, TableInfo
from pixano.features import Item


class TestBaseModelSchema:
    def test_init(self):
        id = "id"
        table_info = TableInfo(name="table", group="views", base_schema="Image")
        data = {}
        BaseModelSchema(id=id, table_info=table_info, data=data)

    def test_from_row(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        item = Item(id="id", split="train")
        model = BaseModelSchema.from_row(item, table_info)

        assert model == BaseModelSchema(id="id", table_info=table_info, data={"split": "train"})

    def test_from_rows(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        items = [Item(id="id1", split="train"), Item(id="id2", split="test")]
        models = BaseModelSchema.from_rows(items, table_info)

        assert models == [
            BaseModelSchema(id="id1", table_info=table_info, data={"split": "train"}),
            BaseModelSchema(id="id2", table_info=table_info, data={"split": "test"}),
        ]

    def test_to_row(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        model = BaseModelSchema(id="id", table_info=table_info, data={"split": "train"})
        item = model.to_row(Item)

        assert item == Item(id="id", split="train")

    def test_to_rows(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        models = [
            BaseModelSchema(id="id1", table_info=table_info, data={"split": "train"}),
            BaseModelSchema(id="id2", table_info=table_info, data={"split": "test"}),
        ]
        items = BaseModelSchema.to_rows(models, Item)

        assert items == [
            Item(id="id1", split="train"),
            Item(id="id2", split="test"),
        ]
