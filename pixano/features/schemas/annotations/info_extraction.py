# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import warnings

from pydantic import model_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict

from ...types.schema_reference import AnnotationRef, EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class NamedEntity(Annotation):
    """Observation of a named-entity in a text.

    Attributes:
        concept_id: id of named-entity type.
        mention: named-entity observed mention.
        spans_start: List of start offsets of the spans in the text.
        spans_end: List of end offsets of the spans in the text.
    """

    concept_id: str
    mention: str
    spans_start: list[int]
    spans_end: list[int]

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(self.spans_start) != len(self.spans_end):
            raise ValueError("Spans offset lists should have the same length")
        if len(self.spans_start) == 0:
            warnings.warn("To ground a NamedEntity in a text, spans offsets should not be empty", category=UserWarning)
        if not all(span[0] >= 0 and span[1] >= 0 for span in zip(self.spans_start, self.spans_end)):
            raise ValueError("Spans offset must be positive")
        if not all(span[0] <= span[1] for span in zip(self.spans_start, self.spans_end)):
            raise ValueError("End offsets must be greater or equal to their corresponding start offset")
        return self

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            "None" NamedEntity.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            concept_id="",
            mention="",
            spans_start=[],
            spans_end=[],
        )

    @property
    def spans(self) -> list[tuple[int, int]]:
        """Get the list of zipped spans offsets (starts and ends)."""
        return list(zip(self.spans_start, self.spans_end))

    @property
    def spans_length(self) -> list[int]:
        """Get the computed list of spans lengths."""
        return [e - s for s, e in zip(self.spans_start, self.spans_end)]


@_register_schema_internal
class Relation(Annotation):
    """Observation of a relation between two named entity in a text.

    Attributes:
        predicate_id: id of relation type.
        subject_id: annotation_id of the subject named-entity
        object_id: annotation_id of the object named-entity
    """

    predicate_id: str
    subject_id: AnnotationRef
    object_id: AnnotationRef

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            "None" Relation.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            predicate_id="",
            subject_id=AnnotationRef.none(),
            object_id=AnnotationRef.none(),
        )


def is_namedentity(cls: type, strict: bool = False) -> bool:
    """Check if a class is a NamedEntity or subclass of NamedEntity."""
    return issubclass_strict(cls, NamedEntity, strict)


def is_relation(cls: type, strict: bool = False) -> bool:
    """Check if a class is a Relation or subclass of Relation."""
    return issubclass_strict(cls, Relation, strict)


def create_namedentity(
    concept_id: str,
    mention: str,
    spans_start: list[int],
    spans_end: list[int],
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> NamedEntity:
    """Create a NamedEntity instance.

    Args:
        concept_id: id of named-entity type.
        mention: named-entity observed mention.
        spans_start: List of start offsets of the spans in the text.
        spans_end: List of end offsets of the spans in the text.
        id: NamedEntity ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `NamedEntity` instance.
    """
    return NamedEntity(
        concept_id=concept_id,
        mention=mention,
        spans_start=spans_start,
        spans_end=spans_end,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )


def create_relation(
    predicate_id: str,
    subject_id: AnnotationRef = AnnotationRef.none(),
    object_id: AnnotationRef = AnnotationRef.none(),
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> Relation:
    """Create a Relation instance.

    Args:
        predicate_id: id of relation type.
        subject_id: annotation_id of the subject named-entity
        object_id: annotation_id of the object named-entity
        id: Relation ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `Relation` instance.
    """
    return Relation(
        predicate_id=predicate_id,
        subject_id=subject_id,
        object_id=object_id,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )
