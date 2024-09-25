# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator
from typing_extensions import TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import Source
from pixano.features.schemas.schema_group import SchemaGroup

from .base_schema import BaseSchemaModel


T = TypeVar("T", bound=Source)


class SourceModel(BaseSchemaModel[Source]):
    """Annotation model."""

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
                        "metadata": '\\{"model_id": "model_0"\\}',
                    },
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.SOURCE.value:
            raise ValueError(f"Table info group must be {SchemaGroup.SOURCE.value}.")
        return value

    def to_row(self, schema_type: type[T]) -> T:
        """Create an annotation from a model."""
        if not issubclass(schema_type, Source):
            raise ValueError(f"Schema type must be a subclass of {Source.__name__}.")
        return super().to_row(schema_type)
