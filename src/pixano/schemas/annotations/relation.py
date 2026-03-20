# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing_extensions import Self

from pixano.utils import issubclass_strict

from .entity_annotation import EntityAnnotation


class Relation(EntityAnnotation):
    """Observation of a relation between two annotations."""

    predicate: str
    subject_id: str = ""
    object_id: str = ""

    @classmethod
    def none(cls) -> Self:
        """Return a Lance-compatible empty relation."""
        return cls(
            id="",
            predicate="",
            subject_id="",
            object_id="",
        )


def is_relation(cls: type, strict: bool = False) -> bool:
    """Check if a class is a ``Relation`` or subclass of ``Relation``."""
    return issubclass_strict(cls, Relation, strict)


def create_relation(
    predicate: str,
    subject_id: str = "",
    object_id: str = "",
    id: str = "",
    record_id: str = "",
    view_id: str = "",
    entity_id: str = "",
    source_type: str = "",
    source_name: str = "",
    source_metadata: str = "{}",
) -> Relation:
    """Create a ``Relation`` instance."""
    return Relation(
        predicate=predicate,
        subject_id=subject_id,
        object_id=object_id,
        id=id,
        record_id=record_id,
        view_id=view_id,
        entity_id=entity_id,
        source_type=source_type,
        source_name=source_name,
        source_metadata=source_metadata,
    )
