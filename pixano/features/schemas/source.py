# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from enum import Enum
from typing import Any, Literal

from pydantic import field_validator, model_validator

from pixano.utils import issubclass_strict

from .base_schema import BaseSchema
from .registry import _register_schema_internal


class SourceKind(Enum):
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


@_register_schema_internal
class Source(BaseSchema):
    """Source of the annotation.

    Attributes:
        name: Name of the source.
        kind: Kind of source.
        metadata: Metadata of the source. dict[str, Any] encoded in a string.
    """

    name: str
    kind: str
    metadata: str = json.dumps({})

    @field_validator("kind", mode="before")
    @classmethod
    def _validate_kind_before(cls, v):
        if isinstance(v, SourceKind):
            v = v.value
        return v

    @field_validator("kind")
    @classmethod
    def _validate_kind_after(cls, v):
        kind_values = [kind.value for kind in SourceKind]
        if v not in kind_values:
            raise ValueError(f"Source kind {v} is not valid. Must be one of {kind_values}.")
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
        if self.kind == SourceKind.GROUND_TRUTH.value:
            if self.name != "Ground Truth":
                raise ValueError("Ground truth source must have name 'Ground Truth'.")
            if self.id != SourceKind.GROUND_TRUTH.value:
                raise ValueError(f"Ground truth source must have id '{SourceKind.GROUND_TRUTH.value}'.")
        return self

    @classmethod
    def create_ground_truth(cls, metadata: str | dict[str, Any] = {}) -> "Source":
        """Create a ground truth source."""
        return cls(
            id=SourceKind.GROUND_TRUTH.value,
            name="Ground Truth",
            kind=SourceKind.GROUND_TRUTH.value,
            metadata=metadata,
        )


def is_source(cls: type, strict: bool = False) -> bool:
    """Check if a class is a Source or subclass of Source."""
    return issubclass_strict(cls, Source, strict)


def create_source(
    id: str,
    name: str,
    kind: Literal["model", "human", "ground_truth", "other"] | SourceKind,
    metadata: str | dict[str, Any],
) -> Source:
    """Create a `Source` instance.

    Args:
        id: Identifier of the source.
        name: Name of the source.
        kind: Kind of source.
        metadata: Metadata of the source.

    Returns:
        The created `Source` instance.
    """
    return Source(id=id, name=name, kind=kind, metadata=metadata)
