# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import TYPE_CHECKING, Generic, TypeVar, Union

from pydantic import ConfigDict, model_validator

from pixano.utils import issubclass_strict

from . import BaseType
from .registry import _register_type_internal


if TYPE_CHECKING:
    from pixano.datasets import Dataset
    from pixano.features import Annotation, BaseSchema, Embedding, Entity, Item, Source, View


T = TypeVar("T", bound=Union["BaseSchema", "Item", "View", "Entity", "Annotation", "Embedding", "Source"])


class SchemaRef(BaseType, Generic[T]):
    """A schema reference.

    A schema reference is used to reference a schema in a dataset. If an id is provided, the reference points to a
    specific element stored in the table associated to the schema.

    Attributes:
        name: The name of the schema.
        id: The id of the schema.
    """

    model_config = ConfigDict(validate_assignment=True)
    name: str
    id: str = ""

    @classmethod
    def none(cls) -> "SchemaRef":
        """Return a reference to no schema."""
        return cls(name="", id="")

    def resolve(self, dataset: "Dataset") -> T:
        """Resolve the reference to the schema."""
        return dataset.resolve_ref(self)


@_register_type_internal
class ItemRef(SchemaRef["Item"]):
    """Item reference."""

    name: str = "item"  # hard coded to avoid circular import

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.name != "item" and (  # hard coded to avoid circular import
            self.name != "" or self.id != ""
        ):
            raise ValueError("name must be 'item' when not empty.")
        return self


@_register_type_internal
class ViewRef(SchemaRef["View"]):
    """View reference."""

    pass


@_register_type_internal
class EntityRef(SchemaRef["Entity"]):
    """Entity reference."""

    pass


@_register_type_internal
class AnnotationRef(SchemaRef["Annotation"]):
    """Annotation reference."""

    pass


@_register_type_internal
class EmbeddingRef(SchemaRef["Embedding"]):
    """Embedding reference."""

    pass


@_register_type_internal
class SourceRef(SchemaRef["Source"]):
    """Source reference."""

    name: str = "source"  # hard coded to avoid circular import

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.name != "source" and (  # hard coded to avoid circular import
            self.name != "" or self.id != ""
        ):
            raise ValueError("name must be 'source' when not empty.")
        return self


def is_schema_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `SchemaRef` or subclass of `SchemaRef`."""
    return issubclass_strict(cls, SchemaRef, strict)


def is_item_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an `ItemRef` or subclass of `ItemRef`."""
    return issubclass_strict(cls, ItemRef, strict)


def is_view_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `ViewRef` or subclass of `ViewRef`."""
    return issubclass_strict(cls, ViewRef, strict)


def is_entity_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an `EntityRef` or subclass of `EntityRef`."""
    return issubclass_strict(cls, EntityRef, strict)


def is_annotation_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an `AnnotationRef` or subclass of `AnnotationRef`."""
    return issubclass_strict(cls, AnnotationRef, strict)


def is_embedding_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is an `EmbeddingRef` or subclass of `EmbeddingRef`."""
    return issubclass_strict(cls, EmbeddingRef, strict)


def is_source_ref(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `SourceRef` or subclass of `SourceRef`."""
    return issubclass_strict(cls, SourceRef, strict)


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


def create_source_ref(id: str) -> SourceRef:
    """Create a source reference."""
    return SourceRef(id=id)
