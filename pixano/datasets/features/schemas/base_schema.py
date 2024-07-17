# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from types import GenericAlias
from typing import Any

from lancedb.pydantic import LanceModel
from pydantic import ConfigDict, create_model

from pixano.datasets.utils.python import get_super_type_from_dict, issubclass_strict

from ..types.registry import _TYPES_REGISTRY


class BaseSchema(LanceModel):
    """Base class for all tables."""

    model_config = ConfigDict(validate_assignment=True)
    id: str = ""

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
                else:
                    fields[field_name] = {
                        "type": field.annotation.__name__,
                        "collection": False,
                    }
        json["fields"] = fields
        return json

    @staticmethod
    def deserialize(dataset_schema_json: dict[str, str | dict[str, Any]]) -> type["BaseSchema"]:
        """Unserialize the dataset schema.

        Args:
            dataset_schema_json: Serialized dataset schema

        Returns:
            type[DatasetSchema]: DatasetSchema
        """
        from .registry import _PIXANO_SCHEMA_REGISTRY, _SCHEMA_REGISTRY

        json_fields = dataset_schema_json["fields"]
        if not isinstance(json_fields, dict):
            raise ValueError("Fields should be a dictionary.")

        fields: dict[str, Any] = {}
        for key, value in json_fields.items():
            if value["type"] in _TYPES_REGISTRY:
                type_ = _TYPES_REGISTRY[value["type"]]
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
    """Check if a class is an BaseSchema or subclass of BaseSchema."""
    return issubclass_strict(cls, BaseSchema, strict)
