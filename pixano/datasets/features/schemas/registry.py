# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .base_schema import BaseSchema


_PIXANO_SCHEMA_REGISTRY: dict[str, type[BaseSchema]] = {"BaseSchema": BaseSchema}
_SCHEMA_REGISTRY: dict[str, type[BaseSchema]] = {"BaseSchema": BaseSchema}


def _add_schema_to_registry(schema: type[BaseSchema], registry: dict[str, type[BaseSchema]]) -> None:
    if not issubclass(schema, BaseSchema):
        raise ValueError(f"Schema {schema} must be a subclass of BaseSchema")

    schema_name = schema.__name__
    if schema_name in registry:
        raise ValueError(f"Schema {schema} already registered")
    registry[schema_name] = schema
    return None


def register_schema(cls):
    """Class decorator to register a schema.

    Args:
        cls: The schema to register.
    """
    _add_schema_to_registry(cls, _SCHEMA_REGISTRY)
    return cls


def _register_schema_internal(cls):
    _add_schema_to_registry(cls, _SCHEMA_REGISTRY)
    _add_schema_to_registry(cls, _PIXANO_SCHEMA_REGISTRY)
    return cls
