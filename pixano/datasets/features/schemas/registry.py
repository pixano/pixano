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
from typing import Dict, Type

from .base_schema import BaseSchema


_PIXANO_SCHEMA_REGISTRY: Dict[str, Type[BaseSchema]] = {}
_SCHEMA_REGISTRY: Dict[str, Type[BaseSchema]] = {}


def register_schema(cls) -> type[BaseSchema]:
    """Class decorator to register a schema.

    Args:
        cls: The schema to register.
    """
    if not issubclass(cls, BaseSchema):
        raise ValueError(f"Schema {cls} must be a subclass of BaseSchema")
    schema_name = cls.__name__.lower().replace(" ", "_")
    if schema_name in _SCHEMA_REGISTRY:
        raise ValueError(f"Schema {schema_name} already registered")
    _SCHEMA_REGISTRY[schema_name] = cls
    return cls


def _register_schema_internal(cls) -> type[BaseSchema]:
    if not issubclass(cls, BaseSchema):
        raise ValueError(f"Schema {cls} must be a subclass of BaseSchema")
    schema_name = cls.__name__.lower().replace(" ", "_")
    if schema_name in _PIXANO_SCHEMA_REGISTRY:
        raise ValueError(f"Schema {schema_name} already registered")
    _PIXANO_SCHEMA_REGISTRY[schema_name] = cls
    _SCHEMA_REGISTRY[schema_name] = cls
    return cls
