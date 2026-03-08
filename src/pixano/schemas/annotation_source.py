# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
import json
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from lancedb.pydantic import LanceModel
from pydantic import Field, field_validator, model_validator

from pixano.utils import issubclass_strict


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


class AnnotationSource(LanceModel):
    """Source that produced the annotation.

    Attributes:
        id: Identifier of the annotation source.
        name: Name of the annotation source.
        kind: Kind of annotation source.
        metadata: Metadata of the annotation source. dict[str, Any] encoded as a JSON string.
        created_at: Creation date.
        updated_at: Last modification date.
    """

    id: str = ""
    name: str
    kind: str
    metadata: str = json.dumps({})
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("kind", mode="before")
    @classmethod
    def _validate_kind_before(cls, v):
        if isinstance(v, AnnotationSourceKind):
            v = v.value
        return v

    @field_validator("kind")
    @classmethod
    def _validate_kind_after(cls, v):
        kind_values = [kind.value for kind in AnnotationSourceKind]
        if v not in kind_values:
            raise ValueError(f"Annotation source kind {v} is not valid. Must be one of {kind_values}.")
        return v

    @field_validator("metadata", mode="before")
    @classmethod
    def _validate_metadata(cls, v: str | dict[str, Any]):
        if not isinstance(v, str):
            if not isinstance(v, dict):
                raise ValueError("Metadata must be a dict or string.")
            if not all(isinstance(k, str) for k in v.keys()):
                raise ValueError("Metadata keys must be strings.")
            return json.dumps(v)
        return v

    @field_validator("metadata", mode="after")
    @classmethod
    def _validate_metadata_after(cls, v: str) -> str:
        try:
            json.loads(v)
        except Exception as e:
            raise ValueError("Metadata must be a valid JSON string. Error: " + str(e))
        return v

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.kind == AnnotationSourceKind.GROUND_TRUTH.value:
            if self.name != "Ground Truth":
                raise ValueError("Ground truth source must have name 'Ground Truth'.")
            if self.id != AnnotationSourceKind.GROUND_TRUTH.value:
                raise ValueError(f"Ground truth source must have id '{AnnotationSourceKind.GROUND_TRUTH.value}'.")
        return self

    @classmethod
    def create_ground_truth(cls, metadata: str | dict[str, Any] = {}) -> "AnnotationSource":
        """Create a ground truth annotation source."""
        return cls(
            id=AnnotationSourceKind.GROUND_TRUTH.value,
            name="Ground Truth",
            kind=AnnotationSourceKind.GROUND_TRUTH.value,
            metadata=metadata,
        )


def is_annotation_source(cls: type, strict: bool = False) -> bool:
    """Check if a class is an AnnotationSource or subclass of AnnotationSource."""
    return issubclass_strict(cls, AnnotationSource, strict)


def create_annotation_source(
    id: str,
    name: str,
    kind: Literal["model", "human", "ground_truth", "other"] | AnnotationSourceKind,
    metadata: str | dict[str, Any],
) -> AnnotationSource:
    """Create an `AnnotationSource` instance.

    Args:
        id: Identifier of the annotation source.
        name: Name of the annotation source.
        kind: Kind of annotation source.
        metadata: Metadata of the annotation source.

    Returns:
        The created `AnnotationSource` instance.
    """
    return AnnotationSource(id=id, name=name, kind=kind, metadata=metadata)
