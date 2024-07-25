# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.pydantic import LanceModel
from pydantic import ConfigDict

from pixano.datasets.utils.python import issubclass_strict


class BaseType(LanceModel):
    """Base class for all Pixano types."""

    model_config = ConfigDict(validate_assignment=True)
    pass


def is_base_type(cls: type, strict: bool = False) -> bool:
    """Check if a class is an BaseType or subclass of BaseType."""
    return issubclass_strict(cls, BaseType, strict)
