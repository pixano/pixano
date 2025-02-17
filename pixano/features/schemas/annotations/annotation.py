# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from typing import Any

from pydantic import field_validator

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..base_schema import BaseSchema
from ..entities import Entity
from ..items.item import Item
from ..registry import _register_schema_internal
from ..views.view import View


@_register_schema_internal
class Annotation(BaseSchema):
    """Annotations are used to annotate an entity in a dataset.

    It can refer to an entity, an item, and a view.

    Attributes:
        item_ref: Reference to the annotation's item.
        view_ref: Reference to the annotation's view.
        entity_ref: Reference to the annotation's entity.
        source_ref: Reference to the annotation's source.
        inference_metadata: Metadata of the inference model for the annotation if any.
            dict[str, Any] encoded in a string.
    """

    item_ref: ItemRef = ItemRef.none()
    view_ref: ViewRef = ViewRef.none()
    entity_ref: EntityRef = EntityRef.none()
    source_ref: SourceRef = SourceRef.none()
    inference_metadata: str = json.dumps({})

    @field_validator("inference_metadata", mode="before")
    @classmethod
    def _validate_inference_metadata(cls, v: str | dict[str, Any]) -> str:
        if not isinstance(v, str):
            if not isinstance(v, dict):
                raise ValueError("Metadata must be a dict or string.")
            if not all(isinstance(k, str) for k in v.keys()):
                raise ValueError("Metadata keys must be strings.")
            return json.dumps(v)
        return v

    @property
    def item(self) -> Item:
        """Get the annotation's item."""
        return self.resolve_ref(self.item_ref)

    @property
    def view(self) -> View:
        """Get the annotation's view."""
        return self.resolve_ref(self.view_ref)

    @property
    def entity(self) -> Entity:
        """Get the annotation's entity."""
        return self.resolve_ref(self.entity_ref)


def is_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Annotation or subclass of Annotation."""
    return issubclass_strict(cls, Annotation, strict)
