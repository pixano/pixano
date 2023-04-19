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
from pyarrow import ArrowKeyError

from .features import BBoxType
from .image import CompressedRLEType, Image, ImageType, is_image_type

__all__ = [
    "ImageType",
    "Image",
    "CompressedRLEType",
    "BBoxType",
    "ObjectAnnotationType",
    "is_image_type",
]


def ObjectAnnotationType():
    """PyArrow StructType for the ObjectAnnotation class

    Should remain consistent with pixano.core.models.ObjectAnnotation

    Returns:
        pa.StructType: ObjectAnnotation StructType
    """

    pose_schema = pa.struct(
        [
            pa.field("cam_R_m2c", pa.list_(pa.float64(), list_size=9)),
            pa.field("cam_t_m2c", pa.list_(pa.float64(), list_size=3)),
        ]
    )

    return pa.struct(
        [
            pa.field("id", pa.string()),
            pa.field("view_id", pa.string(), nullable=True),
            # bounding box
            pa.field("bbox", BBoxType(), nullable=True),
            pa.field("bbox_source", pa.string(), nullable=True),
            pa.field("bbox_confidence", pa.float32(), nullable=True),
            pa.field("is_group_of", pa.bool_(), nullable=True),
            pa.field("is_difficult", pa.bool_(), nullable=True),
            pa.field("is_truncated", pa.bool_(), nullable=True),
            # mask
            pa.field("mask", CompressedRLEType(), nullable=True),
            pa.field("mask_source", pa.string(), nullable=True),
            pa.field("area", pa.float32(), nullable=True),
            # 6d poses
            pa.field("pose", pose_schema, nullable=True),
            # Category
            pa.field("category_id", pa.int32(), nullable=True),
            pa.field("category_name", pa.string(), nullable=True),
            pa.field("identity", pa.string(), nullable=True),
        ]
    )


def convert_field(
    field_name: str, field_type: pa.DataType, field_data: list
) -> pa.Array:
    """Convert PyArrow ExtensionTypes properly

    Args:
        field_name (str): Field name
        field_type (pa.DataType): Field target PyArrow format
        field_data (list): Field data in Python format

    Returns:
        pa.Array: Field data in requested PyArrow format
    """

    # If target format is an ExtensionType
    if isinstance(field_type, pa.ExtensionType):
        storage = pa.array(field_data, type=field_type.storage_type)
        return pa.ExtensionArray.from_storage(field_type, storage)

    # If target format is a ListType
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

    # If target format is a StructType
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


def register_extension_types():
    """Register PyArrow ExtensionTypes"""
    types = [
        BBoxType(),
        CompressedRLEType(),
        ImageType(),
    ]
    for t in types:
        try:
            pa.register_extension_type(t)
        except ArrowKeyError:
            # already registered
            pass


def is_number(t: pa.DataType) -> bool:
    return pa.types.is_integer(t) or pa.types.is_floating(t)


register_extension_types()
