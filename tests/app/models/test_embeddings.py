# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import EmbeddingModel, TableInfo
from pixano.features import Embedding, Item


class CustomEmbedding(Embedding):
    vector: list[float]


class TestEmbeddingModel:
    def test_to_row(self):
        table_info = TableInfo(name="embedding", group="embeddings", base_schema="Embedding")
        model = EmbeddingModel(
            id="id",
            table_info=table_info,
            data={
                "item_ref": {"id": "", "name": ""},
                "vector": [0.0, 0.0, 0.0],
            },
        )
        embedding = model.to_row(CustomEmbedding)

        assert embedding == CustomEmbedding(
            id="id",
            item_ref={"id": "", "name": ""},
            vector=[0.0, 0.0, 0.0],
        )

        with pytest.raises(ValueError, match="Schema type must be a subclass of Embedding."):
            model.to_row(Item)

        table_info = TableInfo(name="embedding", group="item", base_schema="Embedding")
        with pytest.raises(ValueError, match="Table info group must be embeddings."):
            model.table_info = table_info
