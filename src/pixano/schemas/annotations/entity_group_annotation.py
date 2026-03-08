# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pixano.utils import issubclass_strict

from ..records import RecordComponent


class EntityGroupAnnotation(RecordComponent):
    """Annotation that references multiple entities.

    Used for annotations like messages in conversations where a single
    annotation can be linked to several entities.

    Attributes:
        entity_ids: IDs of the entities referenced.
        source_id: ID of the annotation source.
        view_id: ID of the view from which the annotation is derived.
    """

    entity_ids: list[str] = []
    source_id: str = ""
    view_id: str = ""


def is_entity_group_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is an EntityGroupAnnotation or subclass."""
    return issubclass_strict(cls, EntityGroupAnnotation, strict)
