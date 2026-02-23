# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from typing import Any

from pydantic import field_validator

from pixano.utils import issubclass_strict

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
        item_id: ID of the annotation's item.
        entity_id: ID of the annotation's entity.
        source_id: ID of the annotation's source.
        view_name: Logical view name / modality.
        frame_id: ID of the referenced media row when annotation is frame-level.
        frame_index: Frame index (denormalized for temporal queries).
        tracklet_id: ID of the tracklet for temporal linkage.
        entity_dynamic_state_id: ID of the entity dynamic state row.
        inference_metadata: Metadata of the inference model for the annotation if any.
            dict[str, Any] encoded in a string.
    """

    item_id: str = ""
    entity_id: str = ""
    source_id: str = ""
    view_name: str = ""
    frame_id: str = ""
    frame_index: int = -1
    tracklet_id: str = ""
    entity_dynamic_state_id: str = ""

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
        if self.item_id == "":
            raise ValueError("item_id is not set.")
        return self.dataset.get_data("item", ids=[self.item_id])[0]

    @property
    def view(self) -> View:
        """Get the annotation's view."""
        if self.frame_id:
            for group, tables in self.dataset.schema.groups.items():
                if getattr(group, "value", "") != "views":
                    continue
                for table_name in tables:
                    view = self.dataset.get_data(table_name, ids=self.frame_id)
                    if view is not None:
                        return view
        if self.view_name == "":
            raise ValueError("view_name is not set.")
        rows = self.dataset.get_data(self.view_name, item_ids=[self.item_id], where=f"id == '{self.frame_id}'")
        if rows == []:
            raise ValueError(f"View '{self.view_name}' with frame_id '{self.frame_id}' not found.")
        return rows[0]

    @property
    def entity(self) -> Entity:
        """Get the annotation's entity."""
        if self.entity_id == "":
            raise ValueError("entity_id is not set.")
        for group, tables in self.dataset.schema.groups.items():
            if getattr(group, "value", "") != "entities":
                continue
            for table_name in tables:
                entity = self.dataset.get_data(table_name, ids=self.entity_id)
                if entity is not None:
                    return entity
        raise ValueError(f"Entity '{self.entity_id}' not found.")


def is_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Annotation or subclass of Annotation."""
    return issubclass_strict(cls, Annotation, strict)
