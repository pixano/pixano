# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator
from typing_extensions import TypeVar

from pixano.datasets import Dataset
from pixano.features import Entity, SchemaGroup, is_entity

from .base_schema import BaseSchemaModel
from .table_info import TableInfo


T = TypeVar("T", bound=Entity)


class EntityModel(BaseSchemaModel[Entity]):
    """Model for the [Entity][pixano.features.Entity] schema."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "cat_n1",
                    "table_info": {"group": "entities", "name": "cats", "base_schema": "Entity"},
                    "data": {
                        "item_ref": {"name": "item", "id": "1"},
                        "view_ref": {"name": "image", "id": "orange_cats"},
                        "parent_ref": {"name": "", "id": ""},
                        "category": "orange",
                    },
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def _validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.ENTITY.value:
            raise ValueError(f"Table info group must be {SchemaGroup.ENTITY.value}.")
        return value

    def to_row(self, dataset: Dataset) -> Entity:
        """Create an [Entity][pixano.features.Entity] from the model."""
        if not is_entity(dataset.schema.schemas[self.table_info.name]):
            raise ValueError(f"Schema type must be a subclass of {Entity.__name__}.")
        return super().to_row(dataset)
