# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.app.models import SourceModel, TableInfo
from pixano.features import Source


class TestSourceModel:
    def test_to_row(self, dataset_image_bboxes_keypoint):
        table_info = TableInfo(name="source", group="source", base_schema="Source")
        model = SourceModel(
            id="id",
            table_info=table_info,
            data={"name": "source_0", "kind": "model", "metadata": {}},
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        source = model.to_row(dataset_image_bboxes_keypoint)

        assert (
            source.model_dump()
            == Source(
                id="id",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                name="source_0",
                kind="model",
            ).model_dump()
        )

        table_info = TableInfo(name="source", group="views", base_schema="Source")
        with pytest.raises(ValueError, match="Table info group must be source."):
            model.table_info = table_info
