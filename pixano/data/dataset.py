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

from pathlib import Path
from typing import Any, Optional

import pyarrow as pa
import pyarrow.dataset as ds
from pydantic import BaseModel, PrivateAttr

from pixano.core.bbox import BBoxType
from pixano.core.camera import CameraType
from pixano.core.compressed_rle import CompressedRLEType
from pixano.core.depth_image import DepthImageType
from pixano.core.embedding import EmbeddingType
from pixano.core.gt_info import GtInfoType
from pixano.core.image import ImageType
from pixano.core.object_annotation import ObjectAnnotationType
from pixano.core.pose import PoseType


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


class DatasetInfo(BaseModel):
    """DatasetInfo

    Attributes:
        id (str): Dataset ID
        name (str): Dataset name
        description (str): Dataset description
        num_elements (int): Number of elements in dataset
        fields (Fields, optional): Dataset fields
        preview (str, optional): Dataset preview
        categories (list[dict], optional): Dataset categories
        model_id (str, optional): Model ID
        model_name (str, optional): Model name
        model_source (str, optional): Model source
        model_info (str, optional): Model info
    """

    id: str
    name: str
    description: str
    fields: Optional[Fields]
    num_elements: Optional[int]
    preview: Optional[str]
    categories: Optional[list[dict]]
    model_id: Optional[str]
    model_name: Optional[str]
    model_source: Optional[str]
    model_info: Optional[str]

    class Config:
        arbitrary_types_allowed = True

    def to_dict(self) -> dict[str, Any]:
        def _value_as_dict(value):
            if isinstance(value, Fields):
                return value.to_dict()
            else:
                return value

        return {attr: _value_as_dict(getattr(self, attr)) for attr in vars(self).keys()}


class Dataset:
    """Dataset class

    Attributes:
        _path (Path): Dataset path
        _info (DatasetInfo): Dataset info
        _partitioning (ds.partitioning): Dataset partitioning
    """

    _partitioning: ds.partitioning = ds.partitioning(
        pa.schema([("split", pa.string())]), flavor="hive"
    )

    def __init__(self, path: Path):
        """Initialize dataset

        Args:
            path (Path): Dataset path
        """

        self._path = path
        self._info = DatasetInfo.parse_file(self._path / "spec.json")

    @property
    def info(self):
        return self._info

    @property
    def path(self):
        return self._path

    @property
    def media_dir(self):
        return self._path / "media"

    def load(self):
        return ds.dataset(self._path / "db", partitioning=self._partitioning)


class InferenceDataset(Dataset):
    """Inference Dataset

    Attributes:
        _path (Path): Dataset path
        _info (DatasetInfo): Dataset info
        _partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(self, path: Path):
        self._path = path
        self._info = DatasetInfo.parse_file(self._path / "infer.json")

    def load(self):
        return ds.dataset(
            self._path, partitioning=self._partitioning, ignore_prefixes=["infer.json"]
        )


class EmbeddingDataset(Dataset):
    """Embedding Dataset

    Attributes:
        _path (Path): Dataset path
        _info (DatasetInfo): Dataset info
        _partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(self, path: Path):
        self._path = path
        self._info = DatasetInfo.parse_file(self._path / "embed.json")

    def load(self):
        return ds.dataset(
            self._path, partitioning=self._partitioning, ignore_prefixes=["embed.json"]
        )
