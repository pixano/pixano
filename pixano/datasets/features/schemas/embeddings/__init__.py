# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .embedding import (
    Embedding,
    ViewEmbedding,
    create_view_embedding_function,
    is_embedding,
    is_view_embedding,
)


__all__ = [
    "Embedding",
    "ViewEmbedding",
    "is_embedding",
    "is_view_embedding",
    "create_view_embedding_function",
]
