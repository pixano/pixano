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

    This class should be inherited by all Pixano types. [BaseSchema][pixano.features.BaseSchema]s can only have a
    primitive type or a `BaseType` attribute.
    """

    model_config = ConfigDict(validate_assignment=True)
    pass


def is_base_type(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `BaseType` or subclass of `BaseType`."""
    return issubclass_strict(cls, BaseType, strict)
