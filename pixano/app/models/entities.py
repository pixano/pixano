# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import field_validator
from typing_extensions import TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import Entity
from pixano.features.schemas.schema_group import _SchemaGroup

from .base_schema import BaseModelSchema


T = TypeVar("T", bound=Entity)


class EntityModel(BaseModelSchema[Entity]):
    """Entity model."""

    @field_validator("table_info")
    @classmethod
    def validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != _SchemaGroup.ENTITY.value:
            raise ValueError(f"Table info group must be {_SchemaGroup.ENTITY.value}.")
        return value

    def to_row(self, schema_type: type[T]) -> T:
        """Create an entity from a model."""
        if not issubclass(schema_type, Entity):
            raise ValueError(f"Schema type must be a subclass of {Entity.__name__}.")
        return super().to_row(schema_type)
