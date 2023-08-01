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

from .all_pixano_types import PixanoType, createPaType


class Camera(PixanoType, BaseModel):
    depth_scale: list[float]
    cam_K: list[float]
    cam_R_w2c: Optional[list[float]]
    cam_t_w2c: Optional[list[float]]

    def __init__(self, depth_scale, cam_K, cam_R_w2c=None, cam_t_w2c=None):
        # Define public attributes through Pydantic BaseModel
        super().__init__(
            depth_scale=depth_scale,
            cam_K=cam_K,
            cam_R_w2c=cam_R_w2c,
            cam_t_w2c=cam_t_w2c,
        )

    @staticmethod
    def to_struct():
        return pa.struct(
            [
                pa.field("depth_scale", pa.float64()),
                pa.field("cam_K", pa.list_(pa.float64())),
                # pa.field("cam_R_w2c", pa.list_(pa.float64())),
                # pa.field("cam_t_w2c", pa.list_(pa.float64())),
            ]
        )


CameraType = createPaType(Camera.to_struct(), "Camera", Camera)
