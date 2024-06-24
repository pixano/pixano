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
    """BaseIntrinsics (TODO: description?).

    Attributes:
        cx_offset_px (float): cx_offset_px
        cy_offset_px (float): cy_offset_px
        img_height_px (int): img_height_px
        img_width_px (int): img_width_px
    """

    cx_offset_px: float
    cy_offset_px: float
    img_height_px: int
    img_width_px: int


class Intrinsics(pydantic.BaseModel):
    """Intrinsics (TODO: description?).

    Attributes:
        c1 (float): c1
        c2 (float): c2
        c3 (float): c3
        c4 (float): c4
        pixel_aspect_ratio (float): pixel_aspect_ratio
    """

    c1: float
    c2: float
    c3: float
    c4: float
    pixel_aspect_ratio: float


class Extrinsics(pydantic.BaseModel):
    """Extrinsics (TODO: description?).

    Attributes:
        pos_x_m (float): pos_x_m
        pos_y_m (float): pos_y_m
        pos_z_m (float): pos_z_m
        rot_x_deg (float): rot_x_deg
        rot_z1_deg (float): rot_z1_deg
        rot_z2_deg (float): rot_z2_deg
    """

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

    @staticmethod
    def none():
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value

        Returns:
            CamCalibration: "None" CamCalibration
        """
        return CamCalibration(
            type="N/A",
            base_intrinsics=BaseIntrinsics(
                cx_offset_px=0.0,
                cy_offset_px=0.0,
                img_height_px=0,
                img_width_px=0,
            ),
            extrinsics=Extrinsics(
                pos_x_m=0.0,
                pos_y_m=0.0,
                pos_z_m=0.0,
                rot_x_deg=0.0,
                rot_z1_deg=0.0,
                rot_z2_deg=0.0,
            ),
            intrinsics=Intrinsics(
                c1=0.0,
                c2=0.0,
                c3=0.0,
                c4=0.0,
                pixel_aspect_ratio=0.0,
            ),
        )
