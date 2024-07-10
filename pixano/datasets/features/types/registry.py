# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .base_type import BaseType


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

_TYPES_REGISTRY: dict[str, type] = {"BaseType": BaseType}
_PIXANO_TYPES_REGISTRY: dict[str, type[BaseType]] = {"BaseType": BaseType}


def _add_type_to_registry(cls, registry: dict[str, type[BaseType]]) -> None:
    if not (cls in _ATOMIC_PYTHON_TYPES or issubclass(cls, BaseType)):
        raise ValueError(f"Table type {type} must be a an atomic python type or " "derive from BaseType.")

    cls_name = cls.__name__
    if cls_name in registry:
        raise ValueError(f"Type {cls} already registered")
    registry[cls_name] = cls
    return None


def _register_type_internal(cls):
    _add_type_to_registry(cls, _TYPES_REGISTRY)
    if issubclass(cls, BaseType):
        _add_type_to_registry(cls, _PIXANO_TYPES_REGISTRY)
    return cls


for python_type in _ATOMIC_PYTHON_TYPES:
    _register_type_internal(python_type)
