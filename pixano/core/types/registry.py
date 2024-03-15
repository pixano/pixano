from typing import Dict, Type

from lancedb.pydantic import LanceModel


_TABLE_TYPE_REGISTRY: Dict[str, Type[LanceModel]] = {}


def _register_table_type_internal(allow_override: bool = False):
    def decorator(table_type: LanceModel):
        if not issubclass(table_type, LanceModel):
            raise ValueError(f"Table type {type} must be a subclass of LanceModel")
        table_type_name = table_type.__name__
        if table_type_name in _TABLE_TYPE_REGISTRY and not allow_override:
            raise ValueError(f"Table type {table_type_name} already registered")
        _TABLE_TYPE_REGISTRY[table_type_name] = table_type
        return table_type

    return decorator


def register_table_type(allow_override: bool = True):
    """Register table type.

    Args:
        allow_override (bool, optional): Allow override. Defaults to False.
    """
    return _register_table_type_internal(allow_override=allow_override)
