import pyarrow as pa
from pixano.core.arrow_types import *

def convert_type(input_type: str) -> pa.DataType:
    """convert string type to pyarrow type

    Args:
        input_type (str): string , can be written as list form : [myType]

    Returns:
        pa.DataType: pyarrow data type or list of data type
    """

    pa_type_mapping = {
        'int': pa.int64(),
        'float': pa.float32(),
        'bool': pa.bool_(),
        'str': pa.string(),
        'bytes': pa.binary(),
        'np.ndarray': pa.list_(pa.float32()),
        'Image': ImageType,
        'DepthImage': DepthImageType,
        'Camera': CameraType,
        'ObjectAnnotation': ObjectAnnotationType,
        'CompressedRLE': CompressedRLEType,
        'Pose': PoseType,
        'BBox': BBoxType,
        'GtInfo': GtInfoType,
        'Embedding': EmbeddingType,
    }

    # str
    if isinstance(input_type, str):
        if input_type.startswith("[") and input_type.endswith("]"):
            return pa.list_(pa_type_mapping[input_type.removeprefix("[").removesuffix("]")])
        return pa_type_mapping[input_type]

class Features:
    def __init__(self, dict: dict[str, str]) -> None:
        self.dict = dict
    
    @staticmethod
    def from_string_dict(features_dict: dict[str,str]) -> 'Features':
        return Features(features_dict)
        
    def to_fields(self) -> list[pa.field]:
        """Convert dict containing python type to arrow schema

        Args:
            types (dict[str, type]): Dict containing type, key as field name, value as type

        Returns:
            pa.schema: Schema in arrow format
        """
        fields = []
        for field_name, field_type in self.dict.items():
            # Convert the field type to PyArrow type
            field = pa.field(field_name, convert_type(field_type), nullable=True)
            fields.append(field)
        return fields
