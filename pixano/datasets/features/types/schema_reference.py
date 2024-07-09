# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import model_validator

from . import BaseType
from .registry import _register_type_internal


@_register_type_internal
class SchemaRef(BaseType, validate_assignment=True):
    """Schema reference class."""

    name: str
    id: str

    @classmethod
    def none(cls) -> "SchemaRef":
        """Return a reference to no schema."""
        return cls(name="", id="")


@_register_type_internal
class ItemRef(SchemaRef):
    """Item reference class."""

    name: str = "item"  # hard coded to avoid circular import

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.name != "item" and (  # hard coded to avoid circular import
            self.name != "" or self.id != ""
        ):
            raise ValueError("Schema must be 'item' when not empty.")
        return self


@_register_type_internal
class ViewRef(SchemaRef):
    """View reference class."""

    pass


@_register_type_internal
class EntityRef(SchemaRef):
    """Entity reference class."""

    pass



@_register_type_internal
class TrackReference(EntityRef):
    """Track reference Lance Model."""

    pass


@_register_type_internal
class AnnotationReference(SchemaRef):
    """Annotation reference class."""

    pass


@_register_type_internal
class EmbeddingRef(SchemaRef):
    """Embedding reference class."""

    pass
