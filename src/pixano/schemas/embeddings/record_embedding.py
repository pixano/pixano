# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Record-level embedding schema for semantic search.

A `RecordEmbedding` stores one plain float vector per record (computed from the record's image
view). Unlike `ViewEmbedding`, it binds NO LanceDB embedding function, so opening the table never
loads an ML model — vectors are supplied directly (the pixano-inference server computes them).
"""

from lancedb.pydantic import Vector
from pydantic import create_model

from .embedding import Embedding


def build_record_embedding_schema(dim: int) -> type[Embedding]:
    """Build a record-embedding schema with a fixed-size float32 vector column.

    Args:
        dim: Embedding vector dimensionality.

    Returns:
        A concrete `Embedding` subclass with ``vector: Vector(dim)`` (an Arrow
        ``fixed_size_list<float32>[dim]`` column that a LanceDB vector index can cover). It is a
        plain `Embedding` (NOT a `ViewEmbedding`), so no embedding function is registered.
    """
    if not isinstance(dim, int) or dim <= 0:
        raise ValueError(f"Embedding dim must be a positive integer, got {dim!r}.")
    return create_model(
        "RecordEmbedding",
        __base__=Embedding,
        vector=(Vector(dim), ...),
    )
