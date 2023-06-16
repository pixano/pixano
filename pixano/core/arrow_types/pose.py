import pyarrow as pa

class Pose:
    def __init__(self, cam_R_m2c:list[float], cam_t_m2c:list[float]):
        self._cam_R_m2c = cam_R_m2c
        self._cam_t_m2c = cam_t_m2c

    @property
    def cam_R_m2c(self) -> list[float]:
        return self._cam_R_m2c
    
    @property
    def cam_t_m2c(self) -> list[float]:
        return self._cam_t_m2c


class PoseType(pa.ExtensionType):
    """Externalized image type containing the URI string in UTF-8"""

    def __init__(self):
        super(PoseType, self).__init__(
            pa.struct(
                [
                    pa.field("cam_R_m2c", pa.list_(pa.float64(), list_size=9)),
                    pa.field("cam_t_m2c", pa.list_(pa.float64(), list_size=3)),
                ]
            ),
            "Pose",
        )

    def __arrow_ext_serialize__(self):
        return b""

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return PoseType()

    def __arrow_ext_scalar_class__(self):
        return PoseScalar

class PoseScalar(pa.ExtensionScalar):
    def as_py(self) -> Pose:
        return Pose(
            self.value["cam_R_m2c"].as_py(),
            self.value["cam_t_m2c"].as_py()
        )
    

def is_pose_type(t: pa.DataType) -> bool:
    """Returns True if value is an instance of PoseType

    Args:
        t (pa.DataType): Value to check

    Returns:
        bool: Type checking response
    """
    return isinstance(t, PoseType)