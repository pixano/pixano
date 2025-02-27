# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator

from pixano.datasets import Dataset
from pixano.features import SchemaGroup, View, is_view

from .base_schema import BaseSchemaModel
from .table_info import TableInfo


class ViewModel(BaseSchemaModel[View]):
    """Model for the [View][pixano.features.View] schema."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "orange_cats",
                    "table_info": {"group": "views", "name": "image", "base_schema": "Image"},
                    "data": {
                        "item_ref": {"name": "item", "id": "1"},
                        "parent_ref": {"name": "", "id": ""},
                        "url": "/path/to/chat/orange_left.jpg",
                        "format": "JPEG",
                        "width": 100,
                        "height": 100,
                    },
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def _validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.VIEW.value:
            raise ValueError(f"Table info group must be {SchemaGroup.VIEW.value}.")
        return value

    def to_row(self, dataset: Dataset) -> View:
        """Create a [View][pixano.features.View] from the model."""
        if not is_view(dataset.schema.schemas[self.table_info.name]):
            raise ValueError(f"Schema type must be a subclass of {View.__name__}.")
        return super().to_row(dataset)
