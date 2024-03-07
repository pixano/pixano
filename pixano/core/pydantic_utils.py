import inspect
from typing import Any, Dict, List, Optional, Tuple, Union, _GenericAlias, Callable

import pyarrow as pa
import pydantic
from lancedb.pydantic import _pydantic_to_field


def _convert_primitive_field(
    data: List[pydantic.BaseModel], name: str, dtype: pa.DataType
) -> pa.Array:
    """
    Convert a primitive field from a list of pydantic.BaseModel objects to a pyarrow.Array.

    Args:
        data (List[pydantic.BaseModel]): The list of pydantic.BaseModel objects.
        name (str): The name of the field to convert.
        dtype (pa.DataType): The desired data type for the converted field.

    Returns:
        pa.Array: The converted field as a pyarrow.Array.
    """
    return pa.array([getattr(d, name) for d in data], type=dtype)


def _conver_list(
    data: List[pydantic.BaseModel], name: str, dtype: pa.DataType
) -> pa.Array:
    """
    Convert a list field from a list of pydantic.BaseModel objects to a pyarrow.Array.

    Args:
        data (List[pydantic.BaseModel]): The list of pydantic.BaseModel objects.
        name (str): The name of the field to convert.
        dtype (pa.DataType): The desired data type for the converted field.

    Returns:
        pa.Array: The converted field as a pyarrow.Array.
    """
    values = []
    offsets = [0]

    for d in data:
        values.extend(getattr(d, name))
        offsets.append(len(values))

    # TODO don't work with list with non privitive elements type
    return pa.ListArray.from_arrays(pa.array(offsets), pa.array(values))


def _convert_fixed_size_list(
    data: List[pydantic.BaseModel], name: str, list_size: int, dtype: pa.DataType
) -> pa.Array:
    """
    Convert a fixed size list field from a list of pydantic.BaseModel objects to a pyarrow.Array.

    Args:
        data (List[pydantic.BaseModel]): The list of pydantic.BaseModel objects.
        name (str): The name of the field to convert.
        list_size (int): The size of the fixed size list.
        dtype (pa.DataType): The data type of the elements in the fixed size list.

    Returns:
        pa.Array: The converted field as a pyarrow.Array.
    """
    arr = [item for d in data for item in getattr(d, name)]
    return pa.FixedSizeListArray.from_arrays(pa.array(arr, type=dtype), list_size)


def _convert_nested_model(data: List[pydantic.BaseModel], name: str) -> pa.StructArray:
    """
    Convert a list of nested Pydantic models to a StructArray.

    Args:
        data (List[pydantic.BaseModel]): The list of Pydantic models.
        name (str): The name of the nested attribute in the models.

    Returns:
        pa.StructArray: The converted StructArray.
    """
    nested_models = [getattr(d, name) for d in data]
    nested_arrays = to_struct_array(nested_models)

    return nested_arrays


def to_struct_array(data: List[pydantic.BaseModel]) -> pa.StructArray:
    """
    Convert a list of Pydantic BaseModels to a StructArray.

    Args:
        data (List[pydantic.BaseModel]): The list of Pydantic BaseModels to convert.

    Returns:
        pa.StructArray: The converted StructArray.
    """

    fields = []
    arrays = []

    for name, field in data[0].model_fields.items():
        pa_field = _pydantic_to_field(name, field)
        fields.append(pa_field)

        if field.annotation in [int, float, str, bool, bytes]:
            arrays.append(_convert_primitive_field(data, name, pa_field.type))

        elif isinstance(field.annotation, _GenericAlias):
            # Handle GenericAlias types
            origin = field.annotation.__origin__
            args = field.annotation.__args__
            if origin == list:
                arrays.append(_conver_list(data, name, pa_field.type))

            # TODO: handle Union and Optional
            # elif origin == Union:
            #     if len(args) == 2 and args[1] == type(None):
            #         return _py_type_to_arrow_type(args[0], field)
            else:
                raise NotImplementedError
        elif inspect.isclass(field.annotation):
            if issubclass(field.annotation, pydantic.BaseModel):
                arrays.append(_convert_nested_model(data, name))
            elif issubclass(field.annotation, FixedSizeListMixin):
                arrays.append(
                    _convert_fixed_size_list(
                        data,
                        name,
                        field.annotation.dim(),
                        field.annotation.value_arrow_type(),
                    )
                )
        else:
            print(f"{name} Unsupported Field")

    return pa.StructArray.from_arrays(arrays, fields=fields)


def list_to_record_batch(data: List[pydantic.BaseModel]) -> pa.RecordBatch:
    """
    Convert a list of Pydantic models to a RecordBatch.

    Args:
        data (List[pydantic.BaseModel]): The list of Pydantic models.

    Returns:
        pa.RecordBatch: The converted RecordBatch.
    """
    arrays = to_struct_array(data)
    print(arrays)
    return pa.RecordBatch.from_struct_array(arrays)


def flatmap_record_batch(data: pa.RecordBatch, func: Callable) -> pa.RecordBatch:
    """
    Apply a function to each row of a RecordBatch.

    Args:
        data (pa.RecordBatch): The RecordBatch to apply the function to.
        func (Callable): The function to apply to each row of the RecordBatch.

    Returns:
        pa.RecordBatch: The RecordBatch with the function applied to each row.
    """
    transformed_data = [x for batch in data.to_pylist() for x in func(batch)]
    return list_to_record_batch(transformed_data)
