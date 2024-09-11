# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator
from typing_extensions import TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import Item
from pixano.features.schemas.schema_group import SchemaGroup

from .base_schema import BaseModelSchema


T = TypeVar("T", bound=Item)


class ItemModel(BaseModelSchema[Item]):
    """Item model."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "1",
                    "table_info": {"group": "item", "name": "item", "base_schema": "Item"},
                    "data": {"split": "train", "source": "source1"},
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.ITEM.value:
            raise ValueError(f"Table info group must be {SchemaGroup.ITEM.value}.")
        return value

    def to_row(self, schema_type: type[T]) -> T:
        """Create an item from a model."""
        if not issubclass(schema_type, Item):
            raise ValueError(f"Schema type must be a subclass of {Item.__name__}.")
        return super().to_row(schema_type)
