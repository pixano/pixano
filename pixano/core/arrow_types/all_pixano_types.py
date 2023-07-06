from abc import ABC, abstractmethod
from typing import Tuple, Type, Callable

import pyarrow as pa

from pixano.core.arrow_types.utils import convert_field, fields


class PixanoType(ABC):

    @abstractmethod
    def to_struct(cls) -> pa.StructType:
        """Abstract method who must return the pyarrow struct corresponding to pixano type

        Raises:
            NotImplementedError: 

        Returns:
            pa.StructType: Struct corresponding to type
        """
        raise NotImplementedError

    def to_dict(self) -> dict[str, any]:
        """Transform type to dict based on pyarrow struct

        Returns:
            dict[str, any]: Dict with field correspond to struct
        """

        #TODO recursively
        return {field.name : getattr(self,field.name) for field in self.to_struct()}


    @classmethod
    def from_dict(cls: Type["PixanoType"], data: dict[str, any]) -> "PixanoType":
        """Instance type from dict

        Args:
            cls (Type[PixanoType]): Type to instance
            data (dict[str, any]): Dict wih args corresponding to constructor

        Returns:
            PixanoType: New instance of type
        """
        return cls(**data)

def createPaType(struct_type: pa.StructType, name:str, pyType:Type) -> pa.DataType:

    class CustomExtensionType(pa.ExtensionType):
        def __init__(self, struct_type: pa.StructType, name:str):
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
            return f'<{name}Type object at {hex(id(self))}>\n{self}'

        class Scalar(pa.ExtensionScalar):
            def as_py(self):

                def as_py_dict(pa_dict) -> dict:
                    """Recusively convert py arrow dict as py dict

                    Args:
                        pa_dict (_type_): dict containing py arrow types

                    Returns:
                        dict: dict with only scalar python types
                    """
                    py_dict = {}
                    for key, value in pa_dict.items():
                        if hasattr(value, 'as_py') and callable(getattr(value, 'as_py')):
                            py_dict[key] = value.as_py()
                        elif isinstance(value, dict):
                            py_dict[key] = as_py_dict(value) 
                    return py_dict

                return pyType.from_dict(as_py_dict(self.value))


        class Array(pa.ExtensionArray):

            def __repr__(self):
                return f'<{name}Array object at {hex(id(self))}>\n{self}'

            @classmethod
            def from_list(cls, lst: list):
                Fields = struct_type
                arrays = []

                for field in Fields:
                    data = []
                    for obj in lst:
                        if obj is not None:
                            if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
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
    
    new_type = CustomExtensionType(struct_type, name)
    try:
        pa.register_extension_type(new_type)
    # If ExtensionType is already registered
    except pa.ArrowKeyError:
        pass
    return new_type
