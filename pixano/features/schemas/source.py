# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from enum import Enum
from typing import Any

from pydantic import field_validator

from pixano.utils.python import issubclass_strict

from .base_schema import BaseSchema
from .registry import _register_schema_internal


class SourceKind(Enum):
    """Kind of source."""

    MODEL = "model"
    HUMAN = "human"
    GROUND_TRUTH = "ground_truth"


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

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, v):
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


def is_source(cls: type, strict: bool = False) -> bool:
    """Check if a class is a Source or subclass of Source."""
    return issubclass_strict(cls, Source, strict)


def create_source(name: str, kind: str, metadata: str) -> Source:
    """Create a `Source` instance.

    Args:
        name: Name of the source.
        kind: Kind of source.
        metadata: Metadata of the source.

    Returns:
        The created `Source` instance.
    """
    return Source(name=name, kind=kind, metadata=metadata)
