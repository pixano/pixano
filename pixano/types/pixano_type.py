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

from abc import ABC, abstractmethod
from typing import Any, Type

import pyarrow as pa
from pydantic import BaseModel

from .utils import convert_field


class PixanoType(ABC, BaseModel):
    """Base class for all Pixano custom types"""

    def to_dict(self) -> dict[str, Any]:
        """Return custom type as dict based on corresponding PyArrow Struct

        Returns:
            dict[str, Any]: Custom type as dict
        """

        def _convert_value_as_dict(value):
            """Recursively convert value to dict if possible"""

            if isinstance(value, PixanoType):
                return value.to_dict()
            elif isinstance(value, dict):
                return {k: _convert_value_as_dict(v) for k, v in value.items()}
            elif isinstance(value, (list, tuple)):
                return [_convert_value_as_dict(item) for item in value]
            else:
                return value

        struct_fields = self.to_struct()
        return {
            field.name: _convert_value_as_dict(getattr(self, field.name))
            for field in struct_fields
        }

    @classmethod
    def from_dict(cls: Type["PixanoType"], data: dict[str, Any]) -> "PixanoType":
        """Instance custom type from dict

        Args:
            cls (Type[PixanoType]): Pixano custom type to instance
            data (dict[str, Any]): Data to instance from

        Returns:
            PixanoType: New instance of Pixano custom type
        """

        return cls(**data)

    @abstractmethod
    def to_struct(cls) -> pa.StructType:
        """Return custom type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        pass


def createPyArrowType(
    struct_type: pa.StructType, name: str, pyType: Type
) -> pa.ExtensionType:
    """Create PyArrow ExtensionType for Pixano custom type

    Args:
        struct_type (pa.StructType): Pixano custom type as PyArrow Struct
        name (str): Pixano custom type name
        pyType (Type): Pixano custom type Python type

    Returns:
        pa.ExtensionType: PyArrow ExtensionType
    """

    class CustomExtensionType(pa.ExtensionType):
        def __init__(self, struct_type: pa.StructType, name: str):
            super().__init__(struct_type, name)

        @classmethod
        def __arrow_ext_deserialize__(cls, storage_type, serialized):
            return cls(struct_type, name)

        def __arrow_ext_serialize__(self):
            return b""

        def __arrow_ext_scalar_class__(self):
            return self.Scalar

        def __arrow_ext_class__(self):
            return self.Array

        def __repr__(self):
            return f"ExtensionType<{name}Type>"

        class Scalar(pa.ExtensionScalar):
            def as_py(self):
                def as_py_dict(pa_dict: dict[str, Any]) -> dict[str, Any]:
                    """Recusively convert dictionary of PyArrow objects to dictionary of Python objects

                    Args:
                        pa_dict (dict[str, Any]): Dictionary of PyArrow objects

                    Returns:
                        dict[str, Any]: Dictionary of Python objects
                    """

                    py_dict = {}
                    for key, value in pa_dict.items():
                        if hasattr(value, "as_py") and callable(
                            getattr(value, "as_py")
                        ):
                            py_dict[key] = value.as_py()
                        elif isinstance(value, dict):
                            py_dict[key] = as_py_dict(value)
                    return py_dict

                return pyType.from_dict(as_py_dict(self.value))

        class Array(pa.ExtensionArray):
            def __repr__(self):
                return f"<{name}Array object at {hex(id(self))}>\n{self}"

            @classmethod
            def from_list(cls, lst: list):
                Fields = struct_type
                arrays = []

                for field in Fields:
                    data = []
                    for obj in lst:
                        if obj is not None:
                            if hasattr(obj, "to_dict") and callable(
                                getattr(obj, "to_dict")
                            ):
                                data.append(obj.to_dict().get(field.name))
                            else:
                                data.append(obj)
                        else:
                            data.append(None)

                    arrays.append(
                        convert_field(
                            field.name,
                            field.type,
                            data,
                        )
                    )
                sto = pa.StructArray.from_arrays(arrays, fields=Fields)
                return pa.ExtensionArray.from_storage(new_type, sto)

            @classmethod
            def from_lists(cls, list: list[list[Type]]) -> pa.ListArray:
                """Return paListArray corresponding to list of list of type

                Args:
                    list (list[list[Type]]): list of list of type

                Returns:
                    pa.ListArray: List array with offset corresponding to list
                """

                offset = [0]
                for sub_list in list:
                    offset.append(len(sub_list) + offset[-1])

                flat_list = [item for sublist in list for item in sublist]
                flat_array = cls.from_list(flat_list)

                return pa.ListArray.from_arrays(
                    offset, flat_array, type=pa.list_(new_type)
                )

    # Create ExtensionType
    pyarrow_type = CustomExtensionType(struct_type, name)

    # Try and register ExtensionType
    try:
        pa.register_extension_type(pyarrow_type)
    # If ExtensionType is already registered
    except pa.ArrowKeyError:
        pass

    return pyarrow_type
