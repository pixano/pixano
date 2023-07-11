import json
from typing import Self
import numpy as np
import pyarrow as pa
from pixano.core.arrow_types import *
from pixano.core.arrow_types.all_pixano_types import PixanoType

def convert_type(type : PixanoType | type | list[type]):
    py_type_mapping = {
        int: pa.int64(),
        float: pa.float64(),
        bool: pa.bool_(),
        str: pa.string(),
        bytes: pa.binary(),
        np.ndarray: pa.list_(pa.float32()),
        Image: ImageType,
        DepthImage: DepthImageType,
        Camera: CameraType,
        ObjectAnnotation: ObjectAnnotationType,
        CompressedRLE: CompressedRLEType,
        Pose: PoseType,
        BBox: BBoxType,
        GtInfo: GtInfoType,
        Embedding: EmbeddingType,
    }

    if isinstance(type, list):
        element_type = convert_type(type[0])
        return pa.list_(element_type)
    return py_type_mapping[type]

class Features:
    def __init__(self, dict) -> None:
        self.features_dict = dict
    
    @staticmethod
    def from_dict(features_dict):
        return Features(features_dict)
    

    def to_json(self, json_file_path):
        """Write schema string to JSON file

        Args:
            schema_string (str): Schema string
            json_file_path (str): Path to the JSON file
        """
        features = {}
        for key, val in self.features_dict.items():
            if isinstance(val ,list):
                features[key] = f'[{val[0].__name__}]'
            else :
                features[key] = val.__name__

        with open(json_file_path, 'w') as f:
            json.dump({'features': features}, f, indent=4)
        
    def to_schema(self):
        """Convert dict containing python type to arrow schema

        Args:
            types (dict[str, type]): Dict containing type, key as field name, value as type

        Returns:
            pa.schema: Schema in arrow format
        """
        fields = []
        for field_name, field_type in self.features_dict.items():
            # Convert the field type to PyArrow type
            arrow_type = convert_type(field_type)
            field = pa.field(field_name, arrow_type, nullable=True)
            fields.append(field)
        return pa.schema(fields)
