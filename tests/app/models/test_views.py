# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.app.models import TableInfo, ViewModel
from pixano.features import Image


class TestViewModel:
    def test_to_row(self, dataset_image_bboxes_keypoint):
        table_info = TableInfo(name="image", group="views", base_schema="Image")
        model = ViewModel(
            id="id",
            table_info=table_info,
            data={
                "item_ref": {"id": "", "name": ""},
                "parent_ref": {"id": "", "name": ""},
                "url": "coco/1.jpg",
                "format": "jpg",
                "width": 100,
                "height": 100,
            },
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        view = model.to_row(dataset_image_bboxes_keypoint)

        assert (
            view.model_dump()
            == Image(
                id="id",
                item_ref={"id": "", "name": ""},
                view_ref={"id": "", "name": ""},
                parent_ref={"id": "", "name": ""},
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                url="coco/1.jpg",
                format="jpg",
                width=100,
                height=100,
            ).model_dump()
        )

        table_info = TableInfo(name="entities", group="views", base_schema="Entity")
        model.table_info = table_info
        with pytest.raises(ValueError, match="Schema type must be a subclass of View."):
            model.to_row(dataset_image_bboxes_keypoint)

        table_info = TableInfo(name="view", group="item", base_schema="View")
        with pytest.raises(ValueError, match="Table info group must be views."):
            model.table_info = table_info
