# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from .base_schema import BaseSchema


_PIXANO_SCHEMA_REGISTRY: dict[str, type[BaseSchema]] = {}
_SCHEMA_REGISTRY: dict[str, type[BaseSchema]] = {}


def _add_schema_to_registry(
    schema: type[BaseSchema], registry: dict[str, type[BaseSchema]]
) -> None:
    if not issubclass(schema, BaseSchema):
        raise ValueError(f"Schema {schema} must be a subclass of BaseSchema")

    schema_name = schema.__name__.lower().replace(" ", "_")
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
