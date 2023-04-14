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
    # Have to be consistent with class ObjectAnnotation (pixano>core>models.py)
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


def convert_field(name, typ, col):
    """pyarrow is unable to convert ExtensionTypes properly in pa.Table.from_pandas"""
    if isinstance(typ, pa.ExtensionType):
        storage = pa.array(col, type=typ.storage_type)
        return pa.ExtensionArray.from_storage(typ, storage)
    elif pa.types.is_list(typ):
        native_arr = pa.array(col)
        if isinstance(native_arr, pa.NullArray):
            return pa.nulls(len(native_arr), typ)
        offsets = native_arr.offsets
        values = native_arr.values.to_numpy(zero_copy_only=False)
        return pa.ListArray.from_arrays(
            offsets, convert_field(f"{name}.elements", typ.value_type, values)
        )
    elif pa.types.is_struct(typ):
        native_arr = pa.array(col)
        if isinstance(native_arr, pa.NullArray):
            return pa.nulls(len(native_arr), typ)
        arrays = []
        for subfield in typ:
            sub_arr = native_arr.field(subfield.name)
            converted = convert_field(
                f"{name}.{subfield.name}",
                subfield.type,
                sub_arr.to_numpy(zero_copy_only=False),
            )
            arrays.append(converted)
        return pa.StructArray.from_arrays(arrays, fields=typ)
    else:
        return pa.array(col, type=typ)


def register_extension_types():
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
