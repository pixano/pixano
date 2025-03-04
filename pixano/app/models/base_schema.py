# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator
from typing_extensions import Self

from pixano.datasets import Dataset
from pixano.features import BaseSchema
from pixano.utils.validation import validate_and_init_create_at_and_update_at

from .table_info import TableInfo


T = TypeVar("T", bound=BaseSchema)


class BaseSchemaModel(BaseModel, Generic[T]):
    """Base schema model.

    This class is a base class for all schema models. It provides methods to convert a row to a model and vice
    versa.

    Attributes:
        id: Unique identifier of the row.
        created_at: The creation date of the row.
        updated_at: The last modification date of the row.
        table_info: Information about the table to which the row belongs.
        data: Dumped data from the Pixano backend row except the id.
    """

    model_config = ConfigDict(validate_assignment=True)
    id: str
    created_at: datetime
    updated_at: datetime
    table_info: TableInfo
    data: dict[str, Any]

    @field_validator("id", mode="after")
    @classmethod
    def _id_validator(cls, v: str) -> str:
        if " " in v:
            raise ValueError("id must not contain spaces")
        return v

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

    def model_dump(self, exclude_timestamps: bool = False, **kwargs: Any) -> dict[str, Any]:
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
        """Create a model from a row.

        Args:
            row: The row to create the model from.
            table_info: The table info of the row.

        Returns:
            The created model.
        """
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
        """Create a list of models from a list of schemas.

        Args:
            rows: The rows to create the models from.
            table_info: The table info of the rows.

        Returns:
            The list of created models.
        """
        return [cls.from_row(row, table_info) for row in rows]

    def to_row(self, dataset: Dataset) -> T:
        """Create a row from the model.

        Args:
            dataset: The dataset of the row.

        Returns:
            The created row.
        """
        schema_dict = self.model_dump()
        schema = dataset.schema.schemas[self.table_info.name]
        row = schema.model_validate(
            {
                "id": schema_dict["id"],
                "created_at": schema_dict["created_at"],
                "updated_at": schema_dict["updated_at"],
                **schema_dict["data"],
            }
        )
        row.dataset = dataset
        row.table_name = self.table_info.name
        return row

    @staticmethod
    def to_rows(models: list["BaseSchemaModel"], dataset: Dataset) -> list[T]:
        """Create a list of rows from a list of models.

        Args:
            models: The models to create the rows from.
            dataset: The dataset of the row.

        Returns:
            The list of created rows.
        """
        return [model.to_row(dataset) for model in models]
