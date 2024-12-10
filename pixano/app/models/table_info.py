# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel, ConfigDict, field_validator

from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.schema_group import SchemaGroup


class TableInfo(BaseModel):
    """The information of a table.

    Attributes:
        name: Table name.
        group: Group of the schema associated with the table.
        base_schema: Base Pixano schema stored in the registry.
    """

    model_config = ConfigDict(validate_assignment=True)
    name: str
    group: str
    base_schema: str

    @field_validator("base_schema")
    @classmethod
    def _must_be_registered(cls, value: str) -> str:
        """Check that the base schema is registered."""
        if value not in _PIXANO_SCHEMA_REGISTRY:
            raise ValueError(f"Schema {value} is not registered.")
        return value

    @field_validator("group")
    @classmethod
    def _must_be_group(cls, value: str) -> str:
        """Check that the group is valid."""
        if not any(value == group.value for group in SchemaGroup):
            raise ValueError(f"Group {value} is not valid.")
        return value
