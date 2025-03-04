# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json

from pydantic import ConfigDict, field_validator
from typing_extensions import Self

from pixano.datasets import Dataset
from pixano.features import SchemaGroup, Source

from .base_schema import BaseSchemaModel
from .table_info import TableInfo


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

    def to_row(self, dataset: Dataset) -> Source:
        """Create a [Source][pixano.features.Source] from the model."""
        schema_dict = self.model_dump()
        row = Source.model_validate(
            {
                "id": schema_dict["id"],
                "created_at": schema_dict["created_at"],
                "updated_at": schema_dict["updated_at"],
                **schema_dict["data"],
            }
        )
        row.dataset = dataset
        row.table_name = self.table_info.name
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
