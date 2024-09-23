# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self

from pixano.features import BaseSchema
from pixano.utils.validation import validate_and_init_create_at_and_update_at

from .table_info import TableInfo


T = TypeVar("T", bound=BaseSchema)
SUB_T = TypeVar("SUB_T", bound=BaseSchema)


class BaseSchemaModel(BaseModel, Generic[T]):
    """Base schema model.

    Attributes:
        id: Identifier.
        table_info: Table information.
        data: Data from the pydantic backend schema except the id.
    """

    model_config = ConfigDict(validate_assignment=True)
    id: str
    created_at: datetime
    updated_at: datetime
    table_info: TableInfo
    data: dict[str, Any]

    def __init__(self, /, created_at: datetime | None = None, updated_at: datetime | None = None, **data: Any):
        """Create a new model by parsing and validating input data from keyword arguments.

        Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
        validated to form a valid model.

        `self` is explicitly positional-only to allow `self` as a field name.

        Args:
            created_at: The creation date of the object.
            updated_at: The last modification date of the object.
            data: The data of the object validated by Pydantic.
        """
        created_at, updated_at = validate_and_init_create_at_and_update_at(created_at, updated_at)
        data.update({"created_at": created_at, "updated_at": updated_at})
        super().__init__(**data)

    def model_dump(self, exclude_timestamps: bool = False, **kwargs):
        """Dump the model to a dictionary.

        Args:
            exclude_timestamps: Exclude timestamps "created_at" and "updated_at" from the model dump. Useful for
                comparing models without timestamps.
            kwargs: Arguments for pydantic `BaseModel.model_dump()`.

        Returns:
            The model dump.
        """
        model_dump = super().model_dump(**kwargs)
        if exclude_timestamps:
            model_dump.pop("created_at", None)
            model_dump.pop("updated_at", None)
        return model_dump

    @classmethod
    def from_row(cls, row: T, table_info: TableInfo) -> Self:
        """Create a model from a schema."""
        model_dict = {}
        data = {}
        for key, value in row.model_dump().items():
            if key in ["id", "created_at", "updated_at"]:
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
        return schema_type.model_validate(
            {
                "id": schema_dict["id"],
                "created_at": schema_dict["created_at"],
                "updated_at": schema_dict["updated_at"],
                **schema_dict["data"],
            }
        )

    @staticmethod
    def to_rows(schemas: list["BaseSchemaModel"], schema_type: type[SUB_T]) -> list[SUB_T]:
        """Create a list of schemas from a list of models."""
        return [schema.to_row(schema_type) for schema in schemas]
