# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel, ConfigDict, model_validator

from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


class BaseIntrinsics(BaseModel):
    """BaseIntrinsics (TODO: description?).

    Attributes:
        cx_offset_px (float): cx_offset_px
        cy_offset_px (float): cy_offset_px
        img_height_px (int): img_height_px
        img_width_px (int): img_width_px
    """

    model_config = ConfigDict(validate_assignment=True)

    cx_offset_px: float
    cy_offset_px: float
    img_height_px: int
    img_width_px: int

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.img_height_px < 0:
            raise ValueError("img_height_px must be positive")
        elif self.img_width_px < 0:
            raise ValueError("img_width_px must be positive")
        elif self.cx_offset_px < 0:
            raise ValueError("cx_offset_px must be positive")
        elif self.cy_offset_px < 0:
            raise ValueError("cy_offset_px must be positive")
        return self


class Intrinsics(BaseModel):
    """Intrinsics (TODO: description?).

    Attributes:
        c1 (float): c1
        c2 (float): c2
        c3 (float): c3
        c4 (float): c4
        pixel_aspect_ratio (float): pixel_aspect_ratio
    """

    model_config = ConfigDict(validate_assignment=True)

    c1: float
    c2: float
    c3: float
    c4: float
    pixel_aspect_ratio: float

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.c1 < 0:
            raise ValueError("c1 must be positive")
        elif self.c2 < 0:
            raise ValueError("c2 must be positive")
        elif self.c3 < 0:
            raise ValueError("c3 must be positive")
        elif self.c4 < 0:
            raise ValueError("c4 must be positive")
        return self


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

    model_config = ConfigDict(validate_assignment=True)

    pos_x_m: float
    pos_y_m: float
    pos_z_m: float
    rot_x_deg: float
    rot_z1_deg: float
    rot_z2_deg: float

    @model_validator(mode="after")
    def _validate_fields(self):
        if self.pos_x_m < 0:
            raise ValueError("pos_x_m must be positive")
        elif self.pos_y_m < 0:
            raise ValueError("pos_y_m must be positive")
        elif self.pos_z_m < 0:
            raise ValueError("pos_z_m must be positive")
        elif self.rot_x_deg < 0:
            raise ValueError("rot_x_deg must be positive")
        elif self.rot_z1_deg < 0:
            raise ValueError("rot_z1_deg must be positive")
        elif self.rot_z2_deg < 0:
            raise ValueError("rot_z2_deg must be positive")
        return self


@_register_schema_internal
class CamCalibration(Annotation):
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

    @classmethod
    def none(cls):
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            CamCalibration: "None" CamCalibration
        """
        return cls(
            id="",
            item_ref=ItemRef.none(),
            view_ref=ViewRef.none(),
            entity_ref=EntityRef.none(),
            type="",
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
    return issubclass_strict(cls, CamCalibration, strict)


def create_cam_calibration(
    type: str,
    base_intrinsics: BaseIntrinsics | None = None,
    extrinsics: Extrinsics | None = None,
    intrinsics: Intrinsics | None = None,
    cx_offset_px: float | None = None,
    cy_offset_px: float | None = None,
    img_height_px: int | None = None,
    img_width_px: int | None = None,
    pos_x_m: float | None = None,
    pos_y_m: float | None = None,
    pos_z_m: float | None = None,
    rot_x_deg: float | None = None,
    rot_z1_deg: float | None = None,
    rot_z2_deg: float | None = None,
    c1: float | None = None,
    c2: float | None = None,
    c3: float | None = None,
    c4: float | None = None,
    pixel_aspect_ratio: float | None = None,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
) -> CamCalibration:
    """Create a CamCalibration instance.

    Args:
        type (str): The type of camera.
        base_intrinsics (BaseIntrinsics | None, optional): The base intrinsics.
        extrinsics (Extrinsics | None, optional): The extrinsics.
        intrinsics (Intrinsics | None, optional): The intrinsics.
        cx_offset_px (float | None, optional): cx_offset_px
        cy_offset_px (float | None, optional): cy_offset_px
        img_height_px (int | None, optional): img_height_px
        img_width_px (int | None, optional): img_width_px
        pos_x_m (float | None, optional): pos_x_m
        pos_y_m (float | None, optional): pos_y_m
        pos_z_m (float | None, optional): pos_z_m
        rot_x_deg (float | None, optional): rot_x_deg
        rot_z1_deg (float | None, optional): rot_z1_deg
        rot_z2_deg (float | None, optional): rot_z2_deg
        c1 (float | None, optional): c1
        c2 (float | None, optional): c2
        c3 (float | None, optional): c3
        c4 (float | None, optional): c4
        pixel_aspect_ratio (float | None, optional): pixel_aspect_ratio
        id (str, optional): CamCalibration ID.
        item_ref (ItemRef, optional): Item reference.
        view_ref (ViewRef, optional): View reference.
        entity_ref (EntityRef, optional): Entity reference.

    Returns:
        CamCalibration: The created CamCalibration instance.
    """
    none_obj_conditions = [
        base_intrinsics is None,
        extrinsics is None,
        intrinsics is None,
    ]
    not_none_obj_conditions = [
        base_intrinsics is not None,
        extrinsics is not None,
        intrinsics is not None,
    ]

    none_field_conditions = [
        cx_offset_px is None,
        cy_offset_px is None,
        img_height_px is None,
        img_width_px is None,
        pos_x_m is None,
        pos_y_m is None,
        pos_z_m is None,
        rot_x_deg is None,
        rot_z1_deg is None,
        rot_z2_deg is None,
        c1 is None,
        c2 is None,
        c3 is None,
        c4 is None,
        pixel_aspect_ratio is None,
    ]

    not_none_field_conditions = [
        cx_offset_px is not None,
        cy_offset_px is not None,
        img_height_px is not None,
        img_width_px is not None,
        pos_x_m is not None,
        pos_y_m is not None,
        pos_z_m is not None,
        rot_x_deg is not None,
        rot_z1_deg is not None,
        rot_z2_deg is not None,
        c1 is not None,
        c2 is not None,
        c3 is not None,
        c4 is not None,
        pixel_aspect_ratio is not None,
    ]

    if not all(none_obj_conditions) and not all(not_none_obj_conditions):
        raise ValueError("base_intrinsics, extrinsics and intrinsics must be all defined or all None")
    elif not all(none_field_conditions) and not all(not_none_field_conditions):
        raise ValueError(
            "cx_offset_px, cy_offset_px, img_height_px, img_width_px, pos_x_m, pos_y_m, pos_z_m, "
            "rot_x_deg, rot_z1_deg, rot_z2_deg, c1, c2, c3, c4 and pixel_aspect_ratio must be all "
            "defined or all None"
        )
    elif any(not_none_obj_conditions) and any(not_none_field_conditions):
        raise ValueError(
            "base_intrinsics, extrinsics and intrinsics must defined or cx_offset_px, cy_offset_px, img_height_px, "
            "img_width_px, pos_x_m, pos_y_m, pos_z_m, rot_x_deg, rot_z1_deg, rot_z2_deg, c1, c2, c3, c4 and "
            "pixel_aspect_ratio must be defined but not both"
        )
    if any(not_none_field_conditions):
        base_intrinsics = BaseIntrinsics(
            cx_offset_px=cx_offset_px,
            cy_offset_px=cy_offset_px,
            img_height_px=img_height_px,
            img_width_px=img_width_px,
        )
        extrinsics = Extrinsics(
            pos_x_m=pos_x_m,
            pos_y_m=pos_y_m,
            pos_z_m=pos_z_m,
            rot_x_deg=rot_x_deg,
            rot_z1_deg=rot_z1_deg,
            rot_z2_deg=rot_z2_deg,
        )
        intrinsics = Intrinsics(
            c1=c1,
            c2=c2,
            c3=c3,
            c4=c4,
            pixel_aspect_ratio=pixel_aspect_ratio,
        )

    return CamCalibration(
        type=type,
        base_intrinsics=base_intrinsics,
        extrinsics=extrinsics,
        intrinsics=intrinsics,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
    )
