# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator

from pixano.datasets import Dataset
from pixano.features import Item, SchemaGroup, is_item

from .base_schema import BaseSchemaModel
from .table_info import TableInfo


class ItemModel(BaseSchemaModel[Item]):
    """Model for the [Item][pixano.features.Item] schema."""

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
    def _validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.ITEM.value:
            raise ValueError(f"Table info group must be {SchemaGroup.ITEM.value}.")
        return value

    def to_row(self, dataset: Dataset) -> Item:
        """Create an [Item][pixano.features.Item] from the model."""
        if not is_item(dataset.schema.schemas[self.table_info.name]):
            raise ValueError(f"Schema type must be a subclass of {Item.__name__}.")
        return super().to_row(dataset)
