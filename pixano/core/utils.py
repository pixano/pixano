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

from pixano.core.image import ImageType
from pixano.core.object_annotation import ObjectAnnotationType
from pixano.core.pixano_type import convert_field


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

def paArray_from_list(list_data:list | list[list], type: pa.ExtensionType | pa.DataType) -> pa.Array:
    """Convert data or data list as pixano or base python type to array 

    Args:
        data (list | list[list]): list of object or list of list of object
        type (pa.ExtensionType | pa.DataType): pyarrow base type or custom extension type

    Raises:
        ValueError: Unknow type

    Returns:
        pa.Array: Array as pyArrow
    """
    if pa.types.is_list(type):
        type = type.value_type

    if isinstance(type, pa.ExtensionType):
        return type.Array.from_pylist(list_data)
    elif isinstance(type, pa.DataType) and not isinstance(type, pa.ExtensionType):
        return pa.array(list_data)
    else:
        raise ValueError("Unknow type")

