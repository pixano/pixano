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

from pixano.core import (
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
    def from_dict(field_dict: dict[str, str]) -> "Fields":
        """Create Fields from string dictionary

        Args:
            field_dict (dict[str, str]): PyArrow fields as string dictionary

        Returns:
            Fields: Fields
        """

        return Fields(**field_dict)

    def to_dict(self) -> dict[str, str]:
        """Return string dictionary for saving to .json

        Returns:
            dict[str, str]: String dictionary
        """

        return self._field_dict

    def to_pyarrow(self) -> list[pa.field]:
        """Convert Fields string dictionary to list of PyArrow fields

        Returns:
            list[pa.fields]: List of PyArrow fields
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

        fields = []
        for field_name, field_type in self._field_dict.items():
            # Convert the field type to PyArrow type
            field = pa.field(field_name, _pyarrow_mapping(field_type), nullable=True)
            fields.append(field)
        return fields
