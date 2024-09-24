# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.pydantic import LanceModel
from pydantic import ConfigDict

from pixano.utils import issubclass_strict


class BaseType(LanceModel):
    """Base class for all Pixano types.

    This class should be inherited by all Pixano types and schemas can only store a primitive type or a
    BaseType.
    """

    model_config = ConfigDict(validate_assignment=True)
    pass


def is_base_type(cls: type, strict: bool = False) -> bool:
    """Check if a class is an BaseType or subclass of BaseType."""
    return issubclass_strict(cls, BaseType, strict)
