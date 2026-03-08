# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pixano.utils import issubclass_strict

from ..records import RecordComponent


class EntityAnnotation(RecordComponent):
    """Entity annotation.

    Attributes:
        entity_id: ID of the entity annotated.
        source_id: ID of the annotation source.
        view_id: ID of the view from which the annotation is derived.
    """

    entity_id: str = ""
    source_id: str = ""
    view_id: str = ""


def is_entity_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is an EntityAnnotation or subclass of EntityAnnotation."""
    return issubclass_strict(cls, EntityAnnotation, strict)
