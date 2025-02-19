# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.app.models import AnnotationModel, TableInfo
from pixano.features import BBox, Item


class TestAnnotationModel:
    def test_to_row(self):
        table_info = TableInfo(name="bbox", group="annotations", base_schema="BBox")
        model = AnnotationModel(
            id="id",
            table_info=table_info,
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
            data={
                "item_ref": {"id": "", "name": ""},
                "view_ref": {"id": "", "name": ""},
                "entity_ref": {"id": "", "name": ""},
                "coords": [0, 0, 0, 0],
                "format": "xywh",
                "is_normalized": False,
                "confidence": -1.0,
                "inference_metadata": {},
            },
        )
        bbox = model.to_row(BBox)

        assert bbox == BBox(
            id="id",
            coords=[0, 0, 0, 0],
            format="xywh",
            is_normalized=False,
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )

        with pytest.raises(ValueError, match="Schema type must be a subclass of Annotation."):
            model.to_row(Item)

        table_info = TableInfo(name="bbox", group="item", base_schema="BBox")
        with pytest.raises(ValueError, match="Table info group must be annotations."):
            model.table_info = table_info
