# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json

from pydantic import ConfigDict, field_validator
from typing_extensions import Self, TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import Source
from pixano.features.schemas.schema_group import SchemaGroup

from .base_schema import BaseSchemaModel


T = TypeVar("T", bound=Source)


class SourceModel(BaseSchemaModel[Source]):
    """Model for the [Source][pixano.features.Source] schema."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "source_0",
                    "table_info": {"group": "source", "name": "source", "base_schema": "Source"},
                    "data": {
                        "name": "source_0",
                        "kind": "model",
                        "metadata": {"model_id": "model_0"},
                    },
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def _validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.SOURCE.value:
            raise ValueError(f"Table info group must be {SchemaGroup.SOURCE.value}.")
        return value

    def to_row(self, schema_type: type[T]) -> T:
        """Create a [Source][pixano.features.Source] from the model."""
        if not issubclass(schema_type, Source):
            raise ValueError(f"Schema type must be a subclass of {Source.__name__}.")
        row = super().to_row(schema_type)
        row.metadata = json.dumps(self.data["metadata"])
        return row

    @classmethod
    def from_row(cls, row: Source, table_info: TableInfo) -> Self:
        """Create a SourceModel from a Source.

        Args:
            row: The row to create the model from.
            table_info: The table info of the row.

        Returns:
            The created model.
        """
        source_model = BaseSchemaModel.from_row(row, table_info)
        source_model.data["metadata"] = json.loads(source_model.data["metadata"])
        return cls.model_construct(**source_model.__dict__)  # Avoid validation and casting
