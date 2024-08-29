# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self

from pixano.features import BaseSchema

from .table_info import TableInfo


T = TypeVar("T", bound=BaseSchema)
SUB_T = TypeVar("SUB_T", bound=BaseSchema)


class BaseModelSchema(BaseModel, Generic[T]):
    """Base model schema.

    Attributes:
        id: Identifier.
        table_info: Table information.
        data: Data.
    """

    model_config = ConfigDict(validate_assignment=True)
    id: str
    table_info: TableInfo
    data: dict[str, Any]

    @classmethod
    def from_row(cls, row: T, table_info: TableInfo) -> Self:
        """Create a model from a schema."""
        model_dict = {}
        data = {}
        for key, value in row.model_dump().items():
            if key == "id":
                model_dict[key] = value
                continue
            data[key] = value
        model_dict["data"] = data
        model_dict["table_info"] = table_info

        return cls.model_validate(model_dict)

    @classmethod
    def from_rows(cls, rows: list[T], table_info: TableInfo) -> list[Self]:
        """Create a list of models from a list of schemas."""
        return [cls.from_row(row, table_info) for row in rows]

    def to_row(self, schema_type: type[SUB_T]) -> SUB_T:
        """Create a schema from a model."""
        schema_dict = self.model_dump()
        return schema_type.model_validate({"id": schema_dict["id"], **schema_dict["data"]})

    @staticmethod
    def to_rows(schemas: list["BaseModelSchema"], schema_type: type[SUB_T]) -> list[SUB_T]:
        """Create a list of schemas from a list of models."""
        return [schema.to_row(schema_type) for schema in schemas]
