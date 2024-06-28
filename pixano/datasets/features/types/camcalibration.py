# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel

from pixano.datasets.utils import is_obj_of_type

from .registry import _register_type_internal


class BaseIntrinsics(BaseModel):
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


class Intrinsics(BaseModel):
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


class Extrinsics(BaseModel):
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
class CamCalibration(BaseModel):
    """Camera calibration.

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
        Should be removed when Lance could manage None value.

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


def is_cam_calibration(cls: type, strict: bool = False) -> bool:
    """Check if a class is a CamCalibration or subclass of CamCalibration."""
    return is_obj_of_type(cls, CamCalibration, strict)


def create_cam_calibration(
    type: str,
    cx_offset_px: float,
    cy_offset_px: float,
    img_height_px: int,
    img_width_px: int,
    pos_x_m: float,
    pos_y_m: float,
    pos_z_m: float,
    rot_x_deg: float,
    rot_z1_deg: float,
    rot_z2_deg: float,
    c1: float,
    c2: float,
    c3: float,
    c4: float,
    pixel_aspect_ratio: float,
) -> CamCalibration:
    """Create a CamCalibration instance.

    Args:
        type (str): The type of camera.
        cx_offset_px (float): cx_offset_px
        cy_offset_px (float): cy_offset_px
        img_height_px (int): img_height_px
        img_width_px (int): img_width_px
        pos_x_m (float): pos_x_m
        pos_y_m (float): pos_y_m
        pos_z_m (float): pos_z_m
        rot_x_deg (float): rot_x_deg
        rot_z1_deg (float): rot_z1_deg
        rot_z2_deg (float): rot_z2_deg
        c1 (float): c1
        c2 (float): c2
        c3 (float): c3
        c4 (float): c4
        pixel_aspect_ratio (float): pixel_aspect_ratio

    Returns:
        CamCalibration: The created CamCalibration instance.
    """
    return CamCalibration(
        type=type,
        base_intrinsics=BaseIntrinsics(
            cx_offset_px=cx_offset_px,
            cy_offset_px=cy_offset_px,
            img_height_px=img_height_px,
            img_width_px=img_width_px,
        ),
        extrinsics=Extrinsics(
            pos_x_m=pos_x_m,
            pos_y_m=pos_y_m,
            pos_z_m=pos_z_m,
            rot_x_deg=rot_x_deg,
            rot_z1_deg=rot_z1_deg,
            rot_z2_deg=rot_z2_deg,
        ),
        intrinsics=Intrinsics(
            c1=c1,
            c2=c2,
            c3=c3,
            c4=c4,
            pixel_aspect_ratio=pixel_aspect_ratio,
        ),
    )
