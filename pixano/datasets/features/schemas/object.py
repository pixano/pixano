# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.registry import _register_schema_internal
from pixano.datasets.utils import is_obj_of_type

from .base_schema import BaseSchema


@_register_schema_internal
class Object(BaseSchema):
    """Object Lance Model."""

    item_id: str
    view_id: str


def is_object(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Object or subclass of Object."""
    return is_obj_of_type(cls, Object, strict)
