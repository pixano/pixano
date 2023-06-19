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


class Pose:
    """Pose type using orientation and translation matrices

    Attributes:
        _cam_R_m2c (list[float]): 3*3 orientation matrix
        _cam_t_m2c (list[float]): 1*3 translation matrix
    """

    def __init__(self, cam_R_m2c: list[float], cam_t_m2c: list[float]):
        """Initialize pose from orientation and translation matrices

        Args:
            cam_R_m2c (list[float]): 3*3 orientation matrix
            cam_t_m2c (list[float]): 1*3 translation matrix
        """

        self._cam_R_m2c = cam_R_m2c
        self._cam_t_m2c = cam_t_m2c

    @property
    def cam_R_m2c(self) -> list[float]:
        """Returns pose orientation matrix

        Returns:
            list[float]: 3*3 orientation matrix
        """

        return self._cam_R_m2c

    @property
    def cam_t_m2c(self) -> list[float]:
        """Returns pose translation matrix

        Returns:
            list[float]: 1*3 translation matrix
        """

        return self._cam_t_m2c


class PoseType(pa.ExtensionType):
    """Pose type as PyArrow StructType"""

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
        return Pose(self.value["cam_R_m2c"].as_py(), self.value["cam_t_m2c"].as_py())


def is_pose_type(t: pa.DataType) -> bool:
    """Returns True if value is an instance of PoseType

    Args:
        t (pa.DataType): Value to check

    Returns:
        bool: Type checking response
    """

    return isinstance(t, PoseType)
