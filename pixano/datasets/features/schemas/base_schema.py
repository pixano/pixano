# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from types import GenericAlias
from typing import Any

from lancedb.pydantic import LanceModel
from pydantic import create_model

from pixano.datasets.utils.python import get_super_type_from_dict, issubclass_strict

from ..types.registry import _TYPES_REGISTRY


class BaseSchema(LanceModel, validate_assignment=True):
    """Base class for all tables."""

    id: str = ""

    @classmethod
    def serialize(cls):
        """Serialize the table."""
        from .registry import _PIXANO_SCHEMA_REGISTRY

        # schema can be customized by the user
        # base_schema is the closest schema in the registry
        json = {
            "schema": cls.__name__,
            "base_schema": get_super_type_from_dict(cls, _PIXANO_SCHEMA_REGISTRY).__name__,
        }
        fields = {}
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
    def deserialize(dataset_schema_json: dict[str, dict[str, Any]]) -> type["BaseSchema"]:
        """Unserialize the dataset schema.

        Args:
            dataset_schema_json: Serialized dataset schema

        Returns:
            type[DatasetSchema]: DatasetSchema
        """
        from .registry import _PIXANO_SCHEMA_REGISTRY, _SCHEMA_REGISTRY

        fields = {}
        for key, value in dataset_schema_json["fields"].items():
            if value["type"] in _TYPES_REGISTRY:
                type = _TYPES_REGISTRY[value["type"]]
            else:
                raise ValueError(f"Type {value['type']} not registered")
            if value["collection"]:
                type = list[type]
            fields[key] = (type, ...)

        if dataset_schema_json["schema"] in _SCHEMA_REGISTRY:
            table_type = _SCHEMA_REGISTRY[dataset_schema_json["schema"]]
        else:
            table_type = _PIXANO_SCHEMA_REGISTRY[dataset_schema_json["base_schema"]]

        model = create_model(dataset_schema_json["schema"], **fields, __base__=table_type)

        return model


def is_base_schema(cls: type, strict: bool = False) -> bool:
    """Check if a class is an BaseSchema or subclass of BaseSchema."""
    return issubclass_strict(cls, BaseSchema, strict)
