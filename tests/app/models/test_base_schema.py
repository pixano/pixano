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

        with pytest.raises(ValueError, match="id must not contain spaces"):
            BaseSchemaModel(id="id with space", table_info=table_info, data=data)

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

    def test_to_row(self, dataset_image_bboxes_keypoint):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        model = BaseSchemaModel(
            id="id",
            table_info=table_info,
            data={"split": "train", "metadata": "metadata"},
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        item = model.to_row(dataset_image_bboxes_keypoint)

        assert (
            item.model_dump()
            == dataset_image_bboxes_keypoint.schema.schemas["item"](
                id="id",
                split="train",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                metadata="metadata",
            ).model_dump()
        )

    def test_to_rows(self, dataset_image_bboxes_keypoint):
        table_info = TableInfo(name="item", group="item", base_schema="Item")
        models = [
            BaseSchemaModel(
                id="id1",
                table_info=table_info,
                data={"split": "train", "metadata": "metadata"},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            BaseSchemaModel(
                id="id2",
                table_info=table_info,
                data={"split": "test", "metadata": "metadata"},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
        ]
        items = [m.model_dump() for m in BaseSchemaModel.to_rows(models, dataset_image_bboxes_keypoint)]

        assert items == [
            dataset_image_bboxes_keypoint.schema.schemas["item"](
                id="id1",
                split="train",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                metadata="metadata",
            ).model_dump(),
            dataset_image_bboxes_keypoint.schema.schemas["item"](
                id="id2",
                split="test",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                metadata="metadata",
            ).model_dump(),
        ]
