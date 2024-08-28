# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import AnnotationModel, TableInfo
from pixano.features import BBox, Item


class TestAnnotationModel:
    def test_to_row(self):
        table_info = TableInfo(name="bbox", group="annotations", base_schema="BBox")
        model = AnnotationModel(
            id="id",
            table_info=table_info,
            data={
                "item_ref": {"id": "", "name": ""},
                "view_ref": {"id": "", "name": ""},
                "entity_ref": {"id": "", "name": ""},
                "coords": [0, 0, 0, 0],
                "format": "xywh",
                "is_normalized": False,
                "confidence": -1.0,
            },
        )
        bbox = model.to_row(BBox)

        assert bbox == BBox(
            id="id",
            coords=[0, 0, 0, 0],
            format="xywh",
            is_normalized=False,
        )

        with pytest.raises(ValueError, match="Schema type must be a subclass of Annotation."):
            model.to_row(Item)
