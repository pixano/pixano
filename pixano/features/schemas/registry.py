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


def _register_schema_internal():
    def decorator(table_type: type[BaseSchema]):
        if not issubclass(table_type, BaseSchema):
            raise ValueError(f"Table type {type} must be a subclass of BaseSchema")
        table_type_name = table_type.__name__.lower().replace(" ", "_")
        if table_type_name in _PIXANO_SCHEMA_REGISTRY:
            raise ValueError(f"Table type {table_type_name} already registered")
        _PIXANO_SCHEMA_REGISTRY[table_type_name] = table_type
        _SCHEMA_REGISTRY[table_type_name] = table_type
        return table_type

    return decorator


def register_schema():
    """Register table schema."""

    def decorator(table_type: type[BaseSchema]):
        if not issubclass(table_type, BaseSchema):
            raise ValueError(f"Table type {type} must be a subclass of BaseSchema")
        table_type_name = table_type.__name__.lower().replace(" ", "_")
        if table_type_name in _SCHEMA_REGISTRY:
            raise ValueError(f"Table type {table_type_name} already registered")
        _SCHEMA_REGISTRY[table_type_name] = table_type
        return table_type

    return decorator
