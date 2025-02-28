# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.app.models import EmbeddingModel, TableInfo


class TestEmbeddingModel:
    def test_to_row(self, dataset_multi_view_tracking_and_image, view_embedding_8):
        table_info = TableInfo(name="image_embedding", group="embeddings", base_schema="Embedding")
        model = EmbeddingModel(
            id="id",
            table_info=table_info,
            data={
                "item_ref": {"id": "", "name": ""},
                "vector": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "shape": [2, 4],
                "view_ref": {"id": "", "name": ""},
            },
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        embedding = model.to_row(dataset_multi_view_tracking_and_image)

        assert (
            embedding.model_dump()
            == view_embedding_8(
                id="id",
                vector=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ).model_dump()
        )

        table_info = TableInfo(name="image", group="embeddings", base_schema="Image")
        model.table_info = table_info
        with pytest.raises(ValueError, match="Schema type must be a subclass of Embedding."):
            model.to_row(dataset_multi_view_tracking_and_image)

        table_info = TableInfo(name="embedding", group="item", base_schema="Embedding")
        with pytest.raises(ValueError, match="Table info group must be embeddings."):
            model.table_info = table_info
