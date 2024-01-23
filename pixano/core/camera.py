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

from typing import Optional

import pyarrow as pa
from pydantic import BaseModel

from pixano.core.pixano_type import PixanoType, create_pyarrow_type


class Camera(PixanoType, BaseModel):
    """Camera type

    Attributes:
        depth_scale (float): Depth scale
        cam_k (list[float]): Camera matrix K
        cam_r_w2c (list[float], optional): 3*3 orientation matrix
        cam_t_w2c (list[float], optional): 3*1 translation matrix
    """

    depth_scale: float
    cam_k: list[float]
    cam_r_w2c: Optional[list[float]]
    cam_t_w2c: Optional[list[float]]

    def __init__(
        self,
        depth_scale: float,
        cam_k: list[float],
        cam_r_w2c: list[float] = None,
        cam_t_w2c: list[float] = None,
    ):
        """Initialize Camera

        Args:
            depth_scale (float): Depth scale
            cam_k (list[float]): Camera matrix K
            cam_r_w2c (list[float], optional): 3*3 orientation matrix. Defaults to None.
            cam_t_w2c (list[float], optional): 3*1 translation matrix. Defaults to None.
        """

        if cam_r_w2c is None:
            cam_r_w2c = [0.0] * 9
        if cam_t_w2c is None:
            cam_t_w2c = [0.0] * 3

        # Define public attributes through Pydantic BaseModel
        super().__init__(
            depth_scale=depth_scale,
            cam_k=cam_k,
            cam_r_w2c=cam_r_w2c,
            cam_t_w2c=cam_t_w2c,
        )

    @staticmethod
    def to_struct() -> pa.StructType:
        """Return Camera type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        return pa.struct(
            [
                pa.field("depth_scale", pa.float64()),
                pa.field("cam_k", pa.list_(pa.float64())),
                pa.field("cam_r_w2c", pa.list_(pa.float64())),
                pa.field("cam_t_w2c", pa.list_(pa.float64())),
            ]
        )


CameraType = create_pyarrow_type(Camera.to_struct(), "Camera", Camera)
