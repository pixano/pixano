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

import pyarrow as pa
from pydantic import BaseModel, PrivateAttr

from pixano.types import (
    BBoxType,
    CameraType,
    CompressedRLEType,
    DepthImageType,
    EmbeddingType,
    GtInfoType,
    ImageType,
    ObjectAnnotationType,
    PoseType,
)

from .image import ImageType
from .object_annotation import ObjectAnnotationType


class Fields(BaseModel):
    """Dataset PyArrow fields as string dictionary

    Attributes:
        _field_dict: PyArrow fields as string dictionary
    """

    _field_dict: dict[str, str] = PrivateAttr()

    def __init__(self, **data) -> None:
        """Initialize Fields"""

        # Define public attributes through Pydantic BaseModel
        super().__init__()

        # Define private attributes manually
        self._field_dict = {a: data[a] for a in data}

    @staticmethod
    def from_string_dict(field_dict: dict[str, str]) -> "Fields":
        """Create Fields from string dictionary

        Args:
            field_dict (dict[str, str]): PyArrow fields as string dictionary

        Returns:
            Fields: Fields
        """

        return Fields(field_dict)

    def to_fields(self) -> list[pa.field]:
        """Convert Fields string dictionary to list of PyArrow fields

        Returns:
            list[pa.fields]: List of PyArrow fields
        """

        fields = []
        for field_name, field_type in self._field_dict.items():
            # Convert the field type to PyArrow type
            field = pa.field(field_name, convert_type(field_type), nullable=True)
            fields.append(field)
        return fields


def convert_type(input_type: str) -> pa.DataType:
    """Convert string types to PyArrow type

    Args:
        input_type (str): String type. Can be written as list form: [myType]

    Returns:
        pa.DataType: PyArrow DataType or PyArrow list of DataType
    """

    pa_type_mapping = {
        "int": pa.int64(),
        "float": pa.float32(),
        "bool": pa.bool_(),
        "str": pa.string(),
        "bytes": pa.binary(),
        "np.ndarray": pa.list_(pa.float32()),
        "Image": ImageType,
        "DepthImage": DepthImageType,
        "Camera": CameraType,
        "ObjectAnnotation": ObjectAnnotationType,
        "CompressedRLE": CompressedRLEType,
        "Pose": PoseType,
        "BBox": BBoxType,
        "GtInfo": GtInfoType,
        "Embedding": EmbeddingType,
    }

    # str
    if isinstance(input_type, str):
        if input_type.startswith("[") and input_type.endswith("]"):
            return pa.list_(
                pa_type_mapping[input_type.removeprefix("[").removesuffix("]")]
            )
        return pa_type_mapping[input_type]


def convert_field(
    field_name: str, field_type: pa.DataType, field_data: list
) -> pa.Array:
    """Convert PyArrow ExtensionTypes properly

    Args:
        field_name (str): Name
        field_type (pa.DataType): Target PyArrow format
        field_data (list): Data in Python format

    Returns:
        pa.Array: Data in target PyArrow format
    """

    # If target format is an ExtensionType
    if isinstance(field_type, pa.ExtensionType):
        storage = pa.array(field_data, type=field_type.storage_type)
        return pa.ExtensionArray.from_storage(field_type, storage)

    # If target format is an extension of ListType
    elif pa.types.is_list(field_type):
        native_arr = pa.array(field_data)
        if isinstance(native_arr, pa.NullArray):
            return pa.nulls(len(native_arr), field_type)
        offsets = native_arr.offsets
        values = native_arr.values.to_numpy(zero_copy_only=False)
        return pa.ListArray.from_arrays(
            offsets,
            convert_field(f"{field_name}.elements", field_type.value_type, values),
        )

    # If target format is an extension of StructType
    elif pa.types.is_struct(field_type):
        native_arr = pa.array(field_data)
        if isinstance(native_arr, pa.NullArray):
            return pa.nulls(len(native_arr), field_type)
        arrays = []
        for subfield in field_type:
            sub_arr = native_arr.field(subfield.name)
            converted = convert_field(
                f"{field_name}.{subfield.name}",
                subfield.type,
                sub_arr.to_numpy(zero_copy_only=False),
            )
            arrays.append(converted)
        return pa.StructArray.from_arrays(arrays, fields=field_type)

    # For other target formats
    else:
        return pa.array(field_data, type=field_type)


def register_extension_types(pa_types: list[pa.ExtensionType]):
    """Register PyArrow ExtensionTypes

    Args:
        pa_types (list[pa.ExtensionTypes]): List of ExtensionTypes
    """

    for t in pa_types:
        # Register ExtensionType
        try:
            pa.register_extension_type(t())
        # If ExtensionType is already registered
        except pa.ArrowKeyError:
            pass


def fields(struct: pa.StructType) -> list[pa.field]:
    """Return fields of a PyArrow Struct

    Args:
        struct (pa.DataType): PyArrow Struct

    Returns:
        list[pa.field]: List of fields
    """

    fields = []
    for f in range(struct.storage_type.num_fields):
        fields.append(struct.storage_type.field(f))
    return fields


def is_number(t: pa.DataType) -> bool:
    """Check if DataType is a a number (integer or float)

    Args:
        t (pa.DataType): DataType to check

    Returns:
        bool: True if DataType is an integer or a float
    """

    return pa.types.is_integer(t) or pa.types.is_floating(t)


def is_image_type(t: pa.DataType) -> bool:
    """Check if DataType is an Image

    Args:
        t (pa.DataType): DataType to check

    Returns:
        bool: True if DataType is an Image
    """

    return ImageType.equals(t)


def is_list_of_object_annotation_type(t: pa.DataType) -> bool:
    """Check if DataType is a list of ObjectAnnotation

    Args:
        t (pa.DataType): DataType to check

    Returns:
        bool: True if DataType is list of ObjectAnnotation
    """

    return t == pa.list_(ObjectAnnotationType)
