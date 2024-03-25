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

from typing import Type

from pydantic import BaseModel


ATOMIC_PYTHON_TYPES: list[type] = [
    int,
    float,
    complex,
    str,
    bool,
    bytes,
    bytearray,
    memoryview,
]

_TYPES_REGISTRY: dict[str, Type[BaseModel]] = {}


def _add_type_to_registry(cls, registry: dict[str, Type[BaseModel]]) -> None:
    if not (cls in ATOMIC_PYTHON_TYPES or issubclass(cls, BaseModel)):
        raise ValueError(
            f"Table type {type} must be a an atomic python type or "
            "derive from BaseModel."
        )

    cls_name = cls.__name__.lower().replace(" ", "_")
    if cls_name in registry:
        raise ValueError(f"Type {cls} already registered")
    registry[cls_name] = cls
    return None


def _register_type_internal(cls):
    _add_type_to_registry(cls, _TYPES_REGISTRY)
    return cls


for python_type in ATOMIC_PYTHON_TYPES:
    _register_type_internal(python_type)
