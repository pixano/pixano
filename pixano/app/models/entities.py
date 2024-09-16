# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator
from typing_extensions import TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import Entity
from pixano.features.schemas.schema_group import SchemaGroup

from .base_schema import BaseSchemaModel


T = TypeVar("T", bound=Entity)


class EntityModel(BaseSchemaModel[Entity]):
    """Entity model."""

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
    def validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.ENTITY.value:
            raise ValueError(f"Table info group must be {SchemaGroup.ENTITY.value}.")
        return value

    def to_row(self, schema_type: type[T]) -> T:
        """Create an entity from a model."""
        if not issubclass(schema_type, Entity):
            raise ValueError(f"Schema type must be a subclass of {Entity.__name__}.")
        return super().to_row(schema_type)
