from typing import Dict, Type

from lancedb.pydantic import LanceModel
from pydantic import BaseModel


ATOMIC_PYTHON_TYPES = [int, float, complex, str, bool, bytes, bytearray, memoryview]

_TYPES_REGISTRY: Dict[str, Type[LanceModel]] = {}


def _register_type_internal():
    def decorator(type: type[object]):
        if not(type in ATOMIC_PYTHON_TYPES or issubclass(type, BaseModel)):
            raise ValueError(f"Table type {type} must be a an atomic python type or derive from BaseModel.")
        type_name = type.__name__
        if type_name in _TYPES_REGISTRY:
            raise ValueError(f"Type {type_name} already registered")
        _TYPES_REGISTRY[type_name] = type
        return type_name

    return decorator

for python_type in ATOMIC_PYTHON_TYPES:
    _register_type_internal()(python_type)
