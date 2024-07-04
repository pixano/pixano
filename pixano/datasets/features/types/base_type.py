# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.pydantic import LanceModel

from pixano.datasets.utils.python import issubclass_strict


class BaseType(LanceModel, validate_assignment=True):
    """Base class for all Pixano types."""
    pass


def is_base_type(cls: type, strict: bool = False) -> bool:
    """Check if a class is an BaseType or subclass of BaseType."""
    return issubclass_strict(cls, BaseType, strict)
