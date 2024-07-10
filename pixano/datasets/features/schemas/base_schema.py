# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.pydantic import LanceModel

from pixano.datasets.utils.python import issubclass_strict


class BaseSchema(LanceModel, validate_assignment=True):
    """Base class for all tables."""

    id: str = ""


def is_base_schema(cls: type, strict: bool = False) -> bool:
    """Check if a class is an BaseSchema or subclass of BaseSchema."""
    return issubclass_strict(cls, BaseSchema, strict)
