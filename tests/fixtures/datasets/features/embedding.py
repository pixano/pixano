# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from lancedb.embeddings import EmbeddingFunction
from lancedb.pydantic import Vector

from pixano.datasets.features import Embedding, ViewEmbedding
from pixano.datasets.features.schemas.registry import _SCHEMA_REGISTRY, register_schema


@pytest.fixture()
def dumb_embedding_function(vector_size: int = 8):
    class DumbEmbeddingFunction(EmbeddingFunction):
        def compute_query_embeddings(self, queries, *args, **kwargs):
            return [[1, 2, 3, 4, 5, 6, 7, 8]] * len(queries)

        def compute_source_embeddings(self, sources, *args, **kwargs) -> list:
            return [[1, 2, 3, 4, 5, 6, 7, 8]] * len(sources)

        def ndims(self):
            return vector_size

    return DumbEmbeddingFunction


@pytest.fixture()
def embedding_8():
    class Embedding8(Embedding):
        vector: Vector(8)  # type: ignore

    if Embedding8.__name__ not in _SCHEMA_REGISTRY:
        register_schema(Embedding8)

    return Embedding8


@pytest.fixture()
def view_embedding_8():
    class ViewEmbedding8(ViewEmbedding):
        vector: Vector(8)  # type: ignore

    if ViewEmbedding8.__name__ not in _SCHEMA_REGISTRY:
        register_schema(ViewEmbedding8)

    return ViewEmbedding8
