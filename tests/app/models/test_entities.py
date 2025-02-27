# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.app.models import EntityModel, TableInfo
from pixano.features import Entity


class TestEntityModel:
    def test_to_row(self, dataset_image_bboxes_keypoint):
        table_info = TableInfo(name="entities", group="entities", base_schema="Entity")
        model = EntityModel(
            id="id",
            table_info=table_info,
            data={
                "item_ref": {"id": "", "name": ""},
                "view_ref": {"id": "", "name": ""},
                "parent_ref": {"id": "", "name": ""},
            },
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        entity = model.to_row(dataset_image_bboxes_keypoint)

        assert (
            entity.model_dump()
            == Entity(
                id="id",
                item_ref={"id": "", "name": ""},
                view_ref={"id": "", "name": ""},
                parent_ref={"id": "", "name": ""},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ).model_dump()
        )

        table_info = TableInfo(name="image", group="entities", base_schema="Image")
        model.table_info = table_info
        with pytest.raises(ValueError, match="Schema type must be a subclass of Entity."):
            model.to_row(dataset_image_bboxes_keypoint)

        table_info = TableInfo(name="entity", group="item", base_schema="Entity")
        with pytest.raises(ValueError, match="Table info group must be entities."):
            model.table_info = table_info
