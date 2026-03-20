# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ..records import RecordComponent


class Entity(RecordComponent):
    """`Entity` base class.
    Entities are used to define an entity in a dataset such as an object, a track. It can refer to a record
    and a parent entity.

    Attributes:
        parent_id: ID of the parent entity.
    """

    parent_id: str = ""


def is_entity(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Entity or subclass of Entity."""
    return issubclass_strict(cls, Entity, strict)
