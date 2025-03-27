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
class TextSpan(Annotation):
    """Designation of a Text-Span in a text, especially in the
       use-case of Named-Entity Recognition on a Text view
       having a str 'content' attribute.

    Attributes:
        mention: text-span assembled mention.
        spans_start: List of start offsets of the spans in the text.
        spans_end: List of end offsets of the spans in the text.
    """

    mention: str
    spans_start: list[int]
    spans_end: list[int]

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if len(self.spans_start) != len(self.spans_end):
            raise ValueError("Spans offset lists should have the same length")
        if len(self.spans_start) == 0:
            warnings.warn("To ground a TextSpan in a text, spans offsets should not be empty", category=UserWarning)
        if not all(span[0] >= 0 and span[1] >= 0 for span in zip(self.spans_start, self.spans_end)):
            raise ValueError("Spans offset must be positive")
        if not all(span[0] <= span[1] for span in zip(self.spans_start, self.spans_end)):
            raise ValueError("End offsets must be greater or equal to their corresponding start offset")
        return self

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" TextSpan.
        """
        return cls(
            id="",
            item_ref=ItemRef.none(),
            view_ref=ViewRef.none(),
            entity_ref=EntityRef.none(),
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
    """Observation of a relation between two annotations,
       for instance between text-spans in a text.

    Attributes:
        predicate: type of relation, as in semantic-web (OWL, RDF, etc)
        subject_ref: annotation_ref to the subject Annotation (eg TextSpan)
        object_ref: annotation_ref to the object Annotation (eg TextSpan)
    """

    predicate: str
    subject_ref: AnnotationRef
    object_ref: AnnotationRef

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" Relation.
        """
        return cls(
            id="",
            predicate="",
            item_ref=ItemRef.none(),
            view_ref=ViewRef.none(),
            entity_ref=EntityRef.none(),
            subject_ref=AnnotationRef.none(),
            object_ref=AnnotationRef.none(),
        )


def is_text_span(cls: type, strict: bool = False) -> bool:
    """Check if a class is a TextSpan or subclass of TextSpan."""
    return issubclass_strict(cls, TextSpan, strict)


def is_relation(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `Relation` or subclass of `Relation`."""
    return issubclass_strict(cls, Relation, strict)


def create_text_span(
    mention: str,
    spans_start: list[int],
    spans_end: list[int],
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> TextSpan:
    """Create a TextSpan instance.

    Args:
        mention: text-span observed mention.
        spans_start: List of start offsets of the spans in the text.
        spans_end: List of end offsets of the spans in the text.
        id: TextSpan ID.
        item_ref: Item reference.
        view_ref: View reference toward a Text view having a str 'content' attribute.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `TextSpan` instance.
    """
    return TextSpan(
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
    predicate: str,
    subject_ref: AnnotationRef = AnnotationRef.none(),
    object_ref: AnnotationRef = AnnotationRef.none(),
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> Relation:
    """Create a `Relation` instance.

    Args:
        predicate: type of relation
        subject_ref: annotation_ref to the subject TextSpan
        object_ref: annotation_ref to the object TextSpan
        id: Relation ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `Relation` instance.
    """
    return Relation(
        predicate=predicate,
        subject_ref=subject_ref,
        object_ref=object_ref,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )
