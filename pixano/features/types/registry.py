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

from lancedb.pydantic import LanceModel
from pydantic import BaseModel


ATOMIC_PYTHON_TYPES = [int, float, complex, str, bool, bytes, bytearray, memoryview]

_TYPES_REGISTRY: Dict[str, Type[LanceModel]] = {}


def _register_type_internal():
    def decorator(type: type[object]):
        if not (type in ATOMIC_PYTHON_TYPES or issubclass(type, BaseModel)):
            raise ValueError(
                f"Table type {type} must be a an atomic python type or "
                "derive from BaseModel."
            )
        type_name = type.__name__
        if type_name in _TYPES_REGISTRY:
            raise ValueError(f"Type {type_name} already registered")
        _TYPES_REGISTRY[type_name] = type
        return type

    return decorator


for python_type in ATOMIC_PYTHON_TYPES:
    _register_type_internal()(python_type)
