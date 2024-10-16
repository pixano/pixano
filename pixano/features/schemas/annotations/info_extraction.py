# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json

from pydantic import field_validator
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
        spans: List of start-end offset tuples in the text. list[list[int]] encoded in a string.
    """

    concept_id: str
    mention: str
    spans: str

    @field_validator("spans", mode="before")
    @classmethod
    def _validate_spans(cls, v: str | list[list[int]]):
        if isinstance(v, str):
            parsed_v = json.loads(v)
        elif isinstance(v, list):
            parsed_v = v
        else:
            raise ValueError("Spans must be a list of start-end offset tuples, or a JSON dump of such an object.")
        if not isinstance(parsed_v, list):
            raise ValueError("Spans must be a list of start-end offset tuples.")
        if not all(isinstance(tup, list) and len(tup) == 2 for tup in parsed_v):
            raise ValueError(
                "Spans must be a list of start-end offset tuples, each tuple must have 2 positive integer values."
            )
        if not all(all(isinstance(offset, int) for offset in tup) for tup in parsed_v):
            raise ValueError("Spans offset must be positive integers.")
        if not all(tup[0] >= 0 and tup[1] >= 0 for tup in parsed_v):
            raise ValueError("Spans offset must be positive")
        return json.dumps(
            parsed_v,
        )

    @field_validator("spans", mode="after")
    @classmethod
    def _validate_spans_after(cls, v: str) -> str:
        try:
            json.loads(v)
        except Exception as e:
            raise ValueError("Spans must be a valid JSON string. Error: " + str(e))
        return v

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
            spans=json.dumps([]),
        )


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
    spans: str | list[list[int]],
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
        spans: List of start-end offset tuples in the text. list[tuple[int,int]] encoded in a string.
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
        spans=spans,
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
