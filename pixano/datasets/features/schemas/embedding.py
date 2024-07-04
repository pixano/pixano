# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.python import issubclass_strict

from .base_schema import BaseSchema
from .registry import _register_schema_internal


@_register_schema_internal
class Embedding(BaseSchema):
    """Embedding Lance Model."""

    id: str
    item_id: str


def is_embedding(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Embedding or subclass of Embedding."""
    return issubclass_strict(cls, Embedding, strict)
