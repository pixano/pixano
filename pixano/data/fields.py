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

import numpy as np
import pyarrow as pa
from pydantic import BaseModel

from pixano.core import (
    BBox,
    BBoxType,
    Camera,
    CameraType,
    CompressedRLE,
    CompressedRLEType,
    DepthImage,
    DepthImageType,
    GtInfo,
    GtInfoType,
    Image,
    ImageType,
    Pose,
    PoseType,
)


def field_to_python(field: str) -> type:
    """Return Python type from string field

    Args:
        field (str): String field

    Returns:
        type: Python type
    """

    python_dict = {
        "int": int,
        "float": float,
        "bool": bool,
        "str": str,
        "bytes": bytes,
        "np.ndarray": np.ndarray,
        "image": Image,
        "depthimage": DepthImage,
        "camera": Camera,
        "compressedrle": CompressedRLE,
        "pose": Pose,
        "bbox": BBox,
        "gtinfo": GtInfo,
    }

    if isinstance(field, str):
        if field.startswith("[") and field.endswith("]"):
            return list
        if field.startswith("vector(") and field.endswith(")"):
            return np.ndarray
        return python_dict[field.lower()]
    return None


def field_to_pyarrow(field: str) -> pa.DataType:
    """Return PyArrpw type from string field

    Args:
        field (str): String field

    Returns:
        pa.DataType: PyArrow type
    """

    pyarrow_dict = {
        "int": pa.int64(),
        "float": pa.float32(),
        "bool": pa.bool_(),
        "str": pa.string(),
        "bytes": pa.binary(),
        "np.ndarray": pa.list_(pa.float32()),
        "image": ImageType,
        "depthimage": DepthImageType,
        "camera": CameraType,
        "compressedrle": CompressedRLEType,
        "pose": PoseType,
        "bbox": BBoxType,
        "gtinfo": GtInfoType,
    }

    if isinstance(field, str):
        if field.startswith("[") and field.endswith("]"):
            return pa.list_(
                pyarrow_dict[field.removeprefix("[").removesuffix("]").lower()]
            )
        if field.startswith("vector(") and field.endswith(")"):
            size_str = field.removeprefix("vector(").removesuffix(")")
            if size_str.isnumeric():
                return pa.list_(pa.float32(), list_size=int(size_str))
        return pyarrow_dict[field.lower()]
    return None


class Fields(BaseModel):
    """Dataset PyArrow fields as string dictionary

    Attributes:
        field_dict (dict[str, str]): PyArrow fields as string dictionary

    """

    field_dict: dict[str, str]

    def __init__(self, field_dict: dict[str, str]) -> None:
        """Create Fields from string dictionary

        Args:
            field_dict (dict[str, str]): PyArrow fields as string dictionary
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__(field_dict=field_dict)

    def to_schema(self) -> pa.schema:
        """Convert Fields string dictionary to PyArrow schema

        Returns:
            pa.schema: Fields as PyArrow schema
        """
        fields = []
        for field_name, field_type in self.field_dict.items():
            # Convert the field type to PyArrow type
            field = pa.field(field_name, field_to_pyarrow(field_type), nullable=True)
            fields.append(field)
        return pa.schema(fields)
