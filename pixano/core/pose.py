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

from pixano.core.pixano_type import PixanoType, create_pyarrow_type


class Pose(PixanoType, BaseModel):
    """Pose type using orientation and translation matrices

    Attributes:
        _cam_R_m2c (list[float]): 3*3 orientation matrix
        _cam_t_m2c (list[float]): 3*1 translation matrix
    """

    _cam_R_m2c: list[float] = PrivateAttr()
    _cam_t_m2c: list[float] = PrivateAttr()

    def __init__(self, cam_R_m2c: list[float], cam_t_m2c: list[float]):
        """Initialize pose from orientation and translation matrices

        Args:
            cam_R_m2c (list[float]): 3*3 orientation matrix
            cam_t_m2c (list[float]): 3*1 translation matrix
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__()

        # Define private attributes manually
        self._cam_R_m2c = cam_R_m2c
        self._cam_t_m2c = cam_t_m2c

    @property
    def cam_R_m2c(self) -> list[float]:
        """Return Pose orientation matrix

        Returns:
            list[float]: 3*3 orientation matrix
        """

        return self._cam_R_m2c

    @property
    def cam_t_m2c(self) -> list[float]:
        """Return Pose translation matrix

        Returns:
            list[float]: 1*3 translation matrix
        """

        return self._cam_t_m2c

    @staticmethod
    def to_struct() -> pa.StructType:
        """Return Pose type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        return pa.struct(
            [
                pa.field("cam_R_m2c", pa.list_(pa.float64(), list_size=9)),
                pa.field("cam_t_m2c", pa.list_(pa.float64(), list_size=3)),
            ]
        )


PoseType = create_pyarrow_type(Pose.to_struct(), "Pose", Pose)
