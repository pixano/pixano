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


#: Entity columns that link an entity rather than describe it.
ENTITY_SYSTEM_FIELDS = frozenset({"id", "record_id", "parent_id", "created_at", "updated_at"})

#: The fields that name what an entity is, in order of preference. The annotation interface
#: reads an entity's label with the same rule (`resolveEntityLabelField` in `ui/apps/web`), so
#: a class written by a job shows like one typed by a person.
LABEL_FIELD_PRIORITY = ("category", "label", "name", "class")

#: The field a job adds to a dataset whose entities have none to hold a class.
DEFAULT_LABEL_FIELD = "category"


def label_field_of(schema: type[Entity]) -> str | None:
    """The field that holds an entity's class: a known label field, else the first text field.

    Returns:
        The field name, or None when the entities have no text field at all.
    """
    text_fields = [
        name
        for name, field in schema.model_fields.items()
        if name not in ENTITY_SYSTEM_FIELDS and field.annotation is str
    ]
    for candidate in LABEL_FIELD_PRIORITY:
        if candidate in text_fields:
            return candidate
    return text_fields[0] if text_fields else None
