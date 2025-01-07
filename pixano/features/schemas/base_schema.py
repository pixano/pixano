# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

from datetime import datetime
from types import GenericAlias
from typing import TYPE_CHECKING, Any, overload

from lancedb.pydantic import FixedSizeListMixin, LanceModel, Vector
from pydantic import ConfigDict, PrivateAttr, create_model, field_validator
from typing_extensions import Self

from pixano.utils import get_super_type_from_dict, issubclass_strict
from pixano.utils.validation import validate_and_init_create_at_and_update_at

from ..pyarrow_utils import DESERIALIZE_PYARROW_DATATYPE, SERIALIZE_PYARROW_DATATYPE
from ..types.registry import _TYPES_REGISTRY


if TYPE_CHECKING:
    from pixano.datasets.dataset import Dataset
    from pixano.features import (
        Annotation,
        AnnotationRef,
        Embedding,
        EmbeddingRef,
        Entity,
        EntityRef,
        Item,
        ItemRef,
        SchemaRef,
        Source,
        SourceRef,
        View,
        ViewRef,
    )


class BaseSchema(LanceModel):
    """Base class for all schemas.

    All schemas should inherit from this class and therefore all elements in the dataset contains an id.

    Attributes:
        id: the id of the manipulated object.
        created_at: the creation date of the object.
        updated_at: the last modification date of the object.

    Note:
        If the `created_at` and `updated_at` fields are not provided, they are set to the current date and time.
    """

    model_config = ConfigDict(validate_assignment=True)
    id: str = ""
    created_at: datetime
    updated_at: datetime
    _dataset: Dataset | None = PrivateAttr(None)
    _table_name: str = PrivateAttr("")

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

    @property
    def dataset(self) -> Dataset:
        """Get the dataset."""
        if self._dataset is None:
            raise ValueError("Dataset is not set.")
        return self._dataset

    @dataset.setter
    def dataset(self, dataset: Dataset):
        """Set the dataset."""
        self._dataset = dataset

    @property
    def table_name(self) -> str:
        """Get the table name."""
        if self._table_name == "":
            raise ValueError("Table name is not set.")
        return self._table_name

    @table_name.setter
    def table_name(self, table_name: str):
        """Set the table name."""
        self._table_name = table_name

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

    def model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False) -> Self:
        """Returns a copy of the model.

        Args:
            update: Values to change/add in the new model.
            deep: Set to `True` to make a deep copy of the model.

        Returns:
            New model instance.
        """
        # Wrap the pydantic `model_copy` method to prevent copying the dataset.
        dataset = self._dataset
        self._dataset = None

        copy = super().model_copy(update=update, deep=deep)
        copy.dataset = dataset
        return copy

    @overload
    def resolve_ref(self, ref: "ItemRef") -> "Item": ...
    @overload
    def resolve_ref(self, ref: "ViewRef") -> "View": ...
    @overload
    def resolve_ref(self, ref: "EmbeddingRef") -> "Embedding": ...
    @overload
    def resolve_ref(self, ref: "EntityRef") -> "Entity": ...
    @overload
    def resolve_ref(self, ref: "AnnotationRef") -> "Annotation": ...
    @overload
    def resolve_ref(self, ref: "SourceRef") -> "Source": ...
    @overload
    def resolve_ref(self, ref: "SchemaRef") -> "BaseSchema": ...
    def resolve_ref(
        self, ref: "SchemaRef" | "ItemRef" | "ViewRef" | "EmbeddingRef" | "EntityRef" | "AnnotationRef" | "SourceRef"
    ) -> "BaseSchema" | "Item" | "View" | "Embedding" | "Entity" | "Annotation" | "Source":
        """Resolve a reference to a schema object in the dataset.

        Args:
            ref: The reference to resolve.

        Returns:
            The resolved schema object.
        """
        return self.dataset.resolve_ref(ref)

    @classmethod
    def serialize(cls) -> dict[str, str | dict[str, Any]]:
        """Serialize the table."""
        from .registry import _PIXANO_SCHEMA_REGISTRY

        # schema can be customized by the user
        # base_schema is the closest schema in the registry
        super_type = get_super_type_from_dict(cls, _PIXANO_SCHEMA_REGISTRY)
        if super_type is None:
            raise ValueError(f"Schema {cls.__name__} does not have a super type in the registry.")
        json: dict[str, str | dict[str, Any]] = {
            "schema": cls.__name__,
            "base_schema": super_type.__name__,
        }
        fields: dict[str, Any] = {}
        for field_name, field in cls.model_fields.items():
            if isinstance(field.annotation, GenericAlias):
                origin = field.annotation.__origin__
                args = field.annotation.__args__

                if origin in [list, tuple]:
                    if issubclass(args[0], tuple(_TYPES_REGISTRY.values())):
                        fields[field_name] = {
                            "type": args[0].__name__,
                            "collection": True,
                        }
                    else:
                        fields[field_name] = {
                            "type": args[0].__name__,
                            "collection": True,
                        }
                else:
                    raise NotImplementedError("Should be a list or tuple.")
            else:
                if issubclass(field.annotation, tuple(_TYPES_REGISTRY.values())):
                    fields[field_name] = {
                        "type": field.annotation.__name__,
                        "collection": False,
                    }
                elif issubclass(field.annotation, FixedSizeListMixin):  # LanceDB Vector
                    fields[field_name] = {
                        "type": field.annotation.__name__,
                        "collection": False,
                        "dim": field.annotation.dim(),
                        "value_type": SERIALIZE_PYARROW_DATATYPE[field.annotation.value_arrow_type()],
                    }
                else:
                    fields[field_name] = {
                        "type": field.annotation.__name__,
                        "collection": False,
                    }
        json["fields"] = fields
        return json

    @staticmethod
    def deserialize(dataset_schema_json: dict[str, str | dict[str, Any]]) -> type["BaseSchema"]:
        """Deserialize the dataset schema.

        Args:
            dataset_schema_json: Serialized dataset schema.

        Returns:
            The dataset schema.
        """
        from .registry import _PIXANO_SCHEMA_REGISTRY, _SCHEMA_REGISTRY

        json_fields = dataset_schema_json["fields"]
        if not isinstance(json_fields, dict):
            raise ValueError("Fields should be a dictionary.")

        fields: dict[str, Any] = {}
        for key, value in json_fields.items():
            if value["type"] in _TYPES_REGISTRY:
                type_ = _TYPES_REGISTRY[value["type"]]
            elif value["type"] == "FixedSizeList":  # LanceDB Vector
                type_ = value["type"]
                dim = value["dim"]
                value_type = DESERIALIZE_PYARROW_DATATYPE[value["value_type"]]
                type_ = Vector(dim, value_type)
            else:
                raise ValueError(f"Type {value['type']} not registered")
            if value["collection"]:
                type_ = list[type_]  # type: ignore[valid-type]
            fields[key] = (type_, ...)

        schema, base_schema = dataset_schema_json["schema"], dataset_schema_json["base_schema"]

        if not isinstance(schema, str) or not isinstance(base_schema, str):
            raise ValueError("Schema and base schema should be strings.")

        if schema in _SCHEMA_REGISTRY:
            table_type = _SCHEMA_REGISTRY[schema]
        else:
            table_type = _PIXANO_SCHEMA_REGISTRY[base_schema]

        model = create_model(dataset_schema_json["schema"], **fields, __base__=table_type)

        return model


def is_base_schema(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `BaseSchema` or subclass of `BaseSchema`."""
    return issubclass_strict(cls, BaseSchema, strict)
