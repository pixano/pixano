import pyarrow as pa
from pixano.core.arrow_types.all_pixano_types import PixanoType, createPaType


class Camera(PixanoType):
    def __init__(self, cam_K, depth_scale, cam_R_w2c=None, cam_t_w2c=None):
        self.cam_K = cam_K
        self.cam_R_w2c = cam_R_w2c
        self.cam_t_w2c = cam_t_w2c
        self.depth_scale = depth_scale

    @staticmethod
    def to_struct():
        return pa.struct(
            [
                pa.field("cam_K", pa.list_(pa.float64())),
                #pa.field("cam_R_w2c", pa.list_(pa.float64())),
                #pa.field("cam_t_w2c", pa.list_(pa.float64())),
                pa.field("depth_scale", pa.float64()),
            ]
        )


CameraType = createPaType(Camera.to_struct(), 'Camera', Camera)