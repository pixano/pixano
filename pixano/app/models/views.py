# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import field_validator
from typing_extensions import TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import View
from pixano.features.schemas.schema_group import _SchemaGroup

from .base_schema import BaseModelSchema


T = TypeVar("T", bound=View)


class ViewModel(BaseModelSchema[View]):
    """View model."""

    @field_validator("table_info")
    @classmethod
    def validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != _SchemaGroup.VIEW.value:
            raise ValueError(f"Table info group must be {_SchemaGroup.VIEW.value}.")
        return value

    def to_row(self, schema_type: type[T]) -> T:
        """Create a view from a model."""
        if not issubclass(schema_type, View):
            raise ValueError(f"Schema type must be a subclass of {View.__name__}.")
        return super().to_row(schema_type)
