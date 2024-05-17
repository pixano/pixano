# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2024)
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

import pydantic

from .registry import _register_type_internal


class BaseIntrinsics(pydantic.BaseModel):
    cx_offset_px: float
    cy_offset_px: float
    img_height_px: int
    img_width_px: int


class Intrinsics(pydantic.BaseModel):
    c1: float
    c2: float
    c3: float
    c4: float
    pixel_aspect_ratio: float


class Extrinsics(pydantic.BaseModel):
    pos_x_m: float
    pos_y_m: float
    pos_z_m: float
    rot_x_deg: float
    rot_z1_deg: float
    rot_z2_deg: float


@_register_type_internal
class CamCalibration(pydantic.BaseModel):
    """Camera calibration
    Attributes:
        type (str): type of camera
        base_intrinsics (BaseIntrinsics): base intrinsics
        extrinsics (Extrinsics): extrinsics
        intrinsics (Intrinsics): intrinsics
    """
    type: str
    base_intrinsics: BaseIntrinsics
    extrinsics: Extrinsics
    intrinsics: Intrinsics
