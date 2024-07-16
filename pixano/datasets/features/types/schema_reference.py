# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, model_validator

from pixano.datasets.utils.python import issubclass_strict

from . import BaseType
from .registry import _register_type_internal


@_register_type_internal
class SchemaRef(BaseType):
    """Schema reference class."""

    model_config = ConfigDict(validate_assignment=True)
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
class AnnotationRef(SchemaRef):
    """Annotation reference class."""

    pass


@_register_type_internal
class EmbeddingRef(SchemaRef):
    """Embedding reference class."""

    pass


def is_schema_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is a SchemaRef or subclass of SchemaRef."""
    return issubclass_strict(cls, SchemaRef, strict)


def is_item_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an ItemRef or subclass of ItemRef."""
    return issubclass_strict(cls, ItemRef, strict)


def is_view_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is a ViewRef or subclass of ViewRef."""
    return issubclass_strict(cls, ViewRef, strict)


def is_entity_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an EntityRef or subclass of EntityRef."""
    return issubclass_strict(cls, EntityRef, strict)


def is_annotation_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an AnnotationRef or subclass of AnnotationRef."""
    return issubclass_strict(cls, AnnotationRef, strict)


def is_embedding_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an EmbeddingRef or subclass of EmbeddingRef."""
    return issubclass_strict(cls, EmbeddingRef, strict)


def create_schema_ref(id: str, name: str) -> SchemaRef:
    """Create a schema reference."""
    return SchemaRef(name=name, id=id)


def create_item_ref(id: str, name: str = "item") -> ItemRef:
    """Create an item reference."""
    return ItemRef(name=name, id=id)


def create_view_ref(id: str, name: str) -> ViewRef:
    """Create a view reference."""
    return ViewRef(name=name, id=id)


def create_entity_ref(id: str, name: str) -> EntityRef:
    """Create an entity reference."""
    return EntityRef(name=name, id=id)


def create_annotation_ref(id: str, name: str) -> AnnotationRef:
    """Create an annotation reference."""
    return AnnotationRef(name=name, id=id)


def create_embedding_ref(id: str, name: str) -> EmbeddingRef:
    """Create an embedding reference."""
    return EmbeddingRef(name=name, id=id)
