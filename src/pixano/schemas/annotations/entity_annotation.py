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


class EntityAnnotation(RecordComponent):
    """Entity annotation.

    Attributes:
        entity_id: ID of the entity annotated.
        source_type: Kind of annotation source (model, human, ground_truth, other).
        source_name: Name of the annotation source.
        source_metadata: Metadata of the annotation source (JSON string).
        view_id: ID of the view from which the annotation is derived.
    """

    entity_id: str = ""
    source_type: str = ""
    source_name: str = ""
    source_metadata: str = json.dumps({})
    view_id: str = ""

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
