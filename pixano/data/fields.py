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
from pydantic import BaseModel

from pixano.core import (
    BBoxType,
    CameraType,
    CompressedRLEType,
    DepthImageType,
    GtInfoType,
    ImageType,
    PoseType,
)


class Fields(BaseModel):
    """Dataset PyArrow fields as string dictionary

    Attributes:
        field_dict: PyArrow fields as string dictionary
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

        def _pyarrow_mapping(input_type: str) -> pa.DataType:
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
                "image": ImageType,
                "depthimage": DepthImageType,
                "camera": CameraType,
                "compressedrle": CompressedRLEType,
                "pose": PoseType,
                "bbox": BBoxType,
                "gtinfo": GtInfoType,
            }

            # str
            if isinstance(input_type, str):
                if input_type.startswith("[") and input_type.endswith("]"):
                    return pa.list_(
                        pa_type_mapping[
                            input_type.removeprefix("[").removesuffix("]").lower()
                        ]
                    )
                return pa_type_mapping[input_type.lower()]

        fields = []
        for field_name, field_type in self.field_dict.items():
            # Convert the field type to PyArrow type
            field = pa.field(field_name, _pyarrow_mapping(field_type), nullable=True)
            fields.append(field)
        return pa.schema(fields)
