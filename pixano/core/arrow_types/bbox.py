from pixano.transforms.boxes import xywh_to_xyxy, xyxy_to_xywh, normalize, denormalize
import pyarrow as pa



class Bbox:
    """Bbox using xyxy or xywh format"""

    def __init__(self, xyxy:list[float], format:str='xyxy'):
        """create Bbox using xyxy (default) or xywh format

        Args:
            
            xyxy (list[float]): list of float respecting format

            format (str, optional): 'xyxy' or 'xywh'. Defaults to 'xyxy'.
        """

        if format in ['xyxy', 'xywh']:
            self.coords = xyxy
            self.format = format
        else:
            raise ValueError("Invalid format. Supported formats are 'xyxy' and 'xywh'.")
    
    def set_format_xyxy(self):
        """ transform bbox to xyxy format """
        
        if self.format == 'xywh':
            self.coords = xywh_to_xyxy(self.coords)
            self.format = 'xyxy'



    def set_format_xywh(self):
        """ transform bbox to xywh format """
        
        if self.format == 'xyxy':
            self.coords = xyxy_to_xywh(self.coords)
            self.format = 'xywh'


class BBoxType(pa.ExtensionType):
    """Bounding box type as PyArrow list of PyArrow float32"""

    def __init__(self):
        super(BBoxType, self).__init__(
            pa.list_(pa.float32(), list_size=4), "bbox")

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return BBoxType()

    def __arrow_ext_serialize__(self):
        return b""
    
    def __arrow_ext_scalar_class__(self):
        return Bbox
    

def is_bbox_type(obj: pa.DataType) -> bool:
    """Return True if obj is an instance of BboxType

    Args:
        obj (pa.DataType): instance to check

    Returns:
        bool
    """
    return isinstance(obj, BBoxType)