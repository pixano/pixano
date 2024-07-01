# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Type

from pydantic import BaseModel


_ATOMIC_PYTHON_TYPES: list[type] = [
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
    if not (cls in _ATOMIC_PYTHON_TYPES or issubclass(cls, BaseModel)):
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


for python_type in _ATOMIC_PYTHON_TYPES:
    _register_type_internal(python_type)
