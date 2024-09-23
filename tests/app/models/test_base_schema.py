# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.app.models import BaseSchemaModel, TableInfo
from pixano.features import Item


class TestBaseModelSchema:
    def test_init(self):
        id = "id"
        table_info = TableInfo(name="table", group="views", base_schema="Image")
        data = {}
        BaseSchemaModel(id=id, table_info=table_info, data=data)

        with pytest.raises(ValueError, match="Both 'created_at' and 'updated_at' should be set."):
            BaseSchemaModel(created_at=datetime(2021, 1, 1, 0, 0, 0))

        with pytest.raises(ValueError, match="Both 'created_at' and 'updated_at' should be set."):
            BaseSchemaModel(updated_at=datetime(2021, 1, 1, 0, 0, 0))

    def test_from_row(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        item = Item(
            id="id", split="train", created_at=datetime(2021, 1, 1, 0, 0, 0), updated_at=datetime(2021, 1, 1, 0, 0, 0)
        )
        model = BaseSchemaModel.from_row(item, table_info)

        assert model == BaseSchemaModel(
            id="id",
            table_info=table_info,
            data={"split": "train"},
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )

    def test_from_rows(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        items = [
            Item(
                id="id1",
                split="train",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            Item(
                id="id2",
                split="test",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
        ]
        models = BaseSchemaModel.from_rows(items, table_info)

        assert models == [
            BaseSchemaModel(
                id="id1",
                table_info=table_info,
                data={"split": "train"},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            BaseSchemaModel(
                id="id2",
                table_info=table_info,
                data={"split": "test"},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
        ]

    def test_to_row(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        model = BaseSchemaModel(
            id="id",
            table_info=table_info,
            data={"split": "train"},
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        item = model.to_row(Item)

        assert item == Item(
            id="id", split="train", created_at=datetime(2021, 1, 1, 0, 0, 0), updated_at=datetime(2021, 1, 1, 0, 0, 0)
        )

    def test_to_rows(self):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        models = [
            BaseSchemaModel(
                id="id1",
                table_info=table_info,
                data={"split": "train"},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            BaseSchemaModel(
                id="id2",
                table_info=table_info,
                data={"split": "test"},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
        ]
        items = BaseSchemaModel.to_rows(models, Item)

        assert items == [
            Item(
                id="id1",
                split="train",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            Item(
                id="id2",
                split="test",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
        ]
