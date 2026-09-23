# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from enum import Enum
from typing import Any

from pydantic import field_validator

from pixano.utils import issubclass_strict

from ..records import RecordComponent


class AnnotationSourceKind(Enum):
    """Kind of source that produced the annotation.

    Attributes:
        MODEL: Source produced by a model.
        HUMAN: Source produced by a human.
        GROUND_TRUTH: The source is a ground truth.
        OTHER: Source produced by other means.
    """

    MODEL = "model"
    HUMAN = "human"
    GROUND_TRUTH = "ground_truth"
    OTHER = "other"


class ReviewStatus(Enum):
    """Where an annotation produced by a model stands with its human reviewer.

    A human annotation carries no status (the empty string): there is nothing to review. A
    model's output arrives ``pending``; a reviewer accepts it as is, corrects it — the row keeps
    ``source_type = model`` and the model's trace, so corrections can be counted — or rejects
    it, in which case the row stays, marked. A rerun replaces ``pending`` rows only: reviewed
    rows are frozen for that kind. Freezing is not matching: a rerun that detects the same
    object again writes it as a new ``pending`` row next to the reviewed one; telling the two
    apart is the detection kind's concern.

    Attributes:
        PENDING: Produced by a model, not yet reviewed.
        ACCEPTED: Reviewed and kept as is.
        CORRECTED: Reviewed and edited by a human.
        REJECTED: Reviewed and refused; kept, marked.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class EntityAnnotation(RecordComponent):
    """Entity annotation.

    Attributes:
        entity_id: ID of the entity annotated.
        source_type: Kind of annotation source (model, human, ground_truth, other).
        source_name: Name of the annotation source.
        source_metadata: Metadata of the annotation source (JSON string).
        view_id: ID of the view from which the annotation is derived.
        review_status: Review status of a model's output (pending, accepted, corrected,
            rejected); empty for an annotation that was never a model's.
    """

    entity_id: str = ""
    source_type: str = ""
    source_name: str = ""
    source_metadata: str = json.dumps({})
    view_id: str = ""
    review_status: str = ""

    @field_validator("review_status", mode="before")
    @classmethod
    def _validate_review_status_before(cls, v: Any) -> Any:
        if isinstance(v, ReviewStatus):
            return v.value
        return v

    @field_validator("review_status")
    @classmethod
    def _validate_review_status(cls, v: str) -> str:
        if v == "":
            return v
        valid = [k.value for k in ReviewStatus]
        if v not in valid:
            raise ValueError(f"review_status '{v}' is not valid. Must be one of {valid} or empty.")
        return v

    @field_validator("source_type", mode="before")
    @classmethod
    def _validate_source_type_before(cls, v: Any) -> Any:
        if isinstance(v, AnnotationSourceKind):
            return v.value
        return v

    @field_validator("source_type")
    @classmethod
    def _validate_source_type(cls, v: str) -> str:
        if v == "":
            return v
        valid = [k.value for k in AnnotationSourceKind]
        if v not in valid:
            raise ValueError(f"source_type '{v}' is not valid. Must be one of {valid} or empty.")
        return v

    @field_validator("source_metadata", mode="before")
    @classmethod
    def _validate_source_metadata_before(cls, v: str | dict[str, Any]) -> str:
        if isinstance(v, dict):
            if not all(isinstance(k, str) for k in v.keys()):
                raise ValueError("source_metadata keys must be strings.")
            return json.dumps(v)
        return v

    @field_validator("source_metadata")
    @classmethod
    def _validate_source_metadata_after(cls, v: str) -> str:
        try:
            json.loads(v)
        except Exception as e:
            raise ValueError("source_metadata must be a valid JSON string. Error: " + str(e))
        return v


def is_entity_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is an EntityAnnotation or subclass of EntityAnnotation."""
    return issubclass_strict(cls, EntityAnnotation, strict)
