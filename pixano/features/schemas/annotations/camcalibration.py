# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, model_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict

from ...types import BaseType
from ...types.registry import _register_type_internal
from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from . import Annotation


@_register_type_internal
class BaseIntrinsics(BaseType):
    """BaseIntrinsics (TODO: description?).

    Attributes:
        cx_offset_px: cx_offset_px
        cy_offset_px: cy_offset_px
        img_height_px: img_height_px
        img_width_px: img_width_px
    """

    model_config = ConfigDict(validate_assignment=True)

    cx_offset_px: float
    cy_offset_px: float
    img_height_px: int
    img_width_px: int

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if self.img_height_px < 0:
            raise ValueError("img_height_px must be positive")
        elif self.img_width_px < 0:
            raise ValueError("img_width_px must be positive")
        elif self.cx_offset_px < 0:
            raise ValueError("cx_offset_px must be positive")
        elif self.cy_offset_px < 0:
            raise ValueError("cy_offset_px must be positive")
        return self


@_register_type_internal
class Intrinsics(BaseType):
    """Intrinsics (TODO: description?).

    Attributes:
        c1: c1.
        c2: c2.
        c3: c3.
        c4: c4.
        pixel_aspect_ratio: pixel_aspect_ratio.
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


@_register_type_internal
class Extrinsics(BaseType):
    """Extrinsics (TODO: description?).

    Attributes:
        pos_x_m: pos_x_m.
        pos_y_m: pos_y_m.
        pos_z_m: pos_z_m.
        rot_x_deg: rot_x_deg.
        rot_z1_deg: rot_z1_deg.
        rot_z2_deg: rot_z2_deg.
    """

    model_config = ConfigDict(validate_assignment=True)

    pos_x_m: float
    pos_y_m: float
    pos_z_m: float
    rot_x_deg: float
    rot_z1_deg: float
    rot_z2_deg: float

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
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
        type: Type of camera.
        base_intrinsics: Base intrinsics values.
        extrinsics: Extrinsics values.
        intrinsics: Intrinsics values.
    """

    type: str
    base_intrinsics: BaseIntrinsics
    extrinsics: Extrinsics
    intrinsics: Intrinsics

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" `CamCalibration`.
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
    """Check if a class is a `CamCalibration` or subclass of `CamCalibration`."""
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
    source_ref: SourceRef = SourceRef.none(),
    validate: bool = True,
) -> CamCalibration:
    """Create a `CamCalibration` instance.

    Args:
        type: The type of camera.
        base_intrinsics: The base intrinsics.
        extrinsics: The extrinsics.
        intrinsics: The intrinsics.
        cx_offset_px: cx_offset_px.
        cy_offset_px: cy_offset_px.
        img_height_px: img_height_px.
        img_width_px: img_width_px.
        pos_x_m: pos_x_m.
        pos_y_m: pos_y_m.
        pos_z_m: pos_z_m.
        rot_x_deg: rot_x_deg.
        rot_z1_deg: rot_z1_deg.
        rot_z2_deg: rot_z2_deg.
        c1: c1.
        c2: c2.
        c3: c3.
        c4: c4.
        pixel_aspect_ratio: pixel_aspect_ratio.
        id: `CamCalibration` ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.
        validate: Set to False to skip pydantic validation.

    Returns:
        The created `CamCalibration` instance.
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
        if validate:
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
        else:
            base_intrinsics = BaseIntrinsics.construct(
                cx_offset_px=cx_offset_px,
                cy_offset_px=cy_offset_px,
                img_height_px=img_height_px,
                img_width_px=img_width_px,
            )
            extrinsics = Extrinsics.construct(
                pos_x_m=pos_x_m,
                pos_y_m=pos_y_m,
                pos_z_m=pos_z_m,
                rot_x_deg=rot_x_deg,
                rot_z1_deg=rot_z1_deg,
                rot_z2_deg=rot_z2_deg,
            )
            intrinsics = Intrinsics.construct(
                c1=c1,
                c2=c2,
                c3=c3,
                c4=c4,
                pixel_aspect_ratio=pixel_aspect_ratio,
            )

    if validate:
        return CamCalibration(
            type=type,
            base_intrinsics=base_intrinsics,
            extrinsics=extrinsics,
            intrinsics=intrinsics,
            id=id,
            item_ref=item_ref,
            view_ref=view_ref,
            entity_ref=entity_ref,
            source_ref=source_ref,
        )
    else:
        return CamCalibration.construct(
            type=type,
            base_intrinsics=base_intrinsics,
            extrinsics=extrinsics,
            intrinsics=intrinsics,
            id=id,
            item_ref=item_ref,
            view_ref=view_ref,
            entity_ref=entity_ref,
            source_ref=source_ref,
        )
