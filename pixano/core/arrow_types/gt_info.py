import pyarrow as pa
from pixano.core.arrow_types.all_pixano_types import PixanoType, createPaType

from pixano.core.arrow_types.bbox import BBox, BBoxType

class GtInfo(PixanoType):
    def __init__(self, bbox_obj:BBox, bbox_visib:BBox, px_count_all, px_count_valid, px_count_visib, visib_fract):
        self.bbox_obj = bbox_obj
        self.bbox_visib = bbox_visib
        self.px_count_all = px_count_all
        self.px_count_valid = px_count_valid
        self.px_count_visib = px_count_visib
        self.visib_fract = visib_fract
    
    @staticmethod
    def to_struct():
        return pa.struct([
            pa.field('bbox_obj', BBoxType),
            pa.field('bbox_visib', BBoxType),
            pa.field('px_count_all', pa.int64()),
            pa.field('px_count_valid', pa.int64()),
            pa.field('px_count_visib', pa.int64()),
            pa.field('visib_fract', pa.float64())
        ])
    
GtInfoType = createPaType(GtInfo.to_struct(), 'GtInfo', GtInfo)
