
from pixano.transforms.boxes import xywh_to_xyxy, xyxy_to_xywh, normalize
import pyarrow as pa



class BBox:
    """Bbox using xyxy or xywh format"""

    def __init__(self, xyxy:list[float], format:str, is_normalized:bool=True):
        """create Bbox using xyxy or xywh format

        Args:
            
            xyxy (list[float]): list of float respecting format

            format (str): 'xyxy' or 'xywh'. Defaults to 'xyxy'.

            is_normalized (bool, optional). Defaults to True
        """

        self._coords = xyxy
        self._format = format
        self._is_normalized = is_normalized
    
    @classmethod
    def from_xyxy(cls, xyxy: list[float]) -> 'BBox':
        """create Bbox using xyxy format (The coordinates are supposed to be normalized.)

        Args:
            xyxy (list[float]): coords

        Returns:
            Bbox: 
        """
        return BBox(xyxy,'xyxy')
    
    @classmethod
    def from_xywh(cls, xywh: list[float]) -> 'BBox':
        """create Bbox using xywh format (The coordinates are supposed to be normalized.)

        Args:
            xywh (list[float]): coords

        Returns:
            Bbox: 
        """
        return BBox(xywh,'xywh')
    
    @property
    def is_normalized(self) -> bool:
        return self._is_normalized
    
    @property
    def format(self) -> str:
        return self._format
    
    def to_xyxy(self) -> list[float]:
        """get xyxy coords"""
        
        if self._format == 'xywh':
            return xywh_to_xyxy(self._coords)
        return self._coords

    def to_xywh(self) -> list[float]:
        """get xywh coords"""

        if self._format == 'xyxy':
            return xyxy_to_xywh(self._coords)
        return self._coords
 
    def format_xyxy(self):
        """ transform bbox to xyxy format """
        
        if self._format == 'xywh':
            self._coords = xywh_to_xyxy(self._coords)
            self._format = 'xyxy'

    def format_xywh(self):
        """ transform bbox to xywh format """
        
        if self._format == 'xyxy':
            self._coords = xyxy_to_xywh(self._coords)
            self._format = 'xywh'

    def normalize(self, height:int, width:int):
        self._coords = normalize(self._coords, height, width)

    def to_dict(self) -> dict[list[float], bool, str]:
        return {"coords": self._coords, "is_normalized": self._is_normalized, "format": self._format}



class BBoxType(pa.ExtensionType):
    """Bounding box type as PyArrow list of PyArrow float32"""

    def __init__(self):
        super(BBoxType, self).__init__(
            pa.struct(
                [
                    pa.field("coords" ,pa.list_(pa.float32(), list_size=4)),
                    pa.field("is_normalized", pa.bool_()),
                    pa.field("format", pa.string())
                ]
            ),
            "BBox",
            )

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return BBoxType()

    def __arrow_ext_serialize__(self):
        return b""
    
    def __arrow_ext_scalar_class__(self):
        return BBoxScalar
    
    def __arrow_ext_class__(self):
        return BBoxArray
    
class BBoxScalar(pa.ExtensionScalar):
    def as_py(self) -> BBox:
        return BBox(
            self.value["coords"].as_py(),
            self.value["format"].as_py(),
            self.value["is_normalized"].as_py()
        )

class BBoxArray(pa.ExtensionArray):
    
    @classmethod
    def from_BBox_list(cls, bbox_list):
        bbox_dicts = []
        for bbox in bbox_list:
            bbox_dicts.append(bbox.to_dict())
        return pa.array(bbox_dicts, BBoxType())


    

def is_bbox_type(obj: pa.DataType) -> bool:
    """Return True if obj is an instance of BboxType

    Args:
        obj (pa.DataType): instance to check

    Returns:
        bool
    """
    return isinstance(obj, BBoxType)