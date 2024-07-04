# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.features.types.camcalibration import (
    BaseIntrinsics,
    CamCalibration,
    Extrinsics,
    Intrinsics,
    create_cam_calibration,
    is_cam_calibration,
)
from tests.datasets.features.utils import make_tests_is_sublass_strict


class TestCamCalibration:
    def none():
        none_cam_calibration = CamCalibration.none()
        assert none_cam_calibration.type == "N/A"
        assert none_cam_calibration.intrinsics.c1 == 0.0
        assert none_cam_calibration.intrinsics.c2 == 0.0
        assert none_cam_calibration.intrinsics.c3 == 0.0
        assert none_cam_calibration.intrinsics.c4 == 0.0
        assert none_cam_calibration.intrinsics.pixel_aspect_ratio == 0.0
        assert none_cam_calibration.extrinsics.pos_x_m == 0.0
        assert none_cam_calibration.extrinsics.pos_y_m == 0.0
        assert none_cam_calibration.extrinsics.pos_z_m == 0.0
        assert none_cam_calibration.extrinsics.rot_x_deg == 0.0
        assert none_cam_calibration.extrinsics.rot_z1_deg == 0.0
        assert none_cam_calibration.extrinsics.rot_z2_deg == 0.0
        assert none_cam_calibration.base_intrinsics.cx_offset_px == 0.0
        assert none_cam_calibration.base_intrinsics.cy_offset_px == 0.0
        assert none_cam_calibration.base_intrinsics.img_height_px == 0
        assert none_cam_calibration.base_intrinsics.img_width_px == 0


def test_is_cam_calibration():
    make_tests_is_sublass_strict(is_cam_calibration, CamCalibration)


def test_create_cam_calibration():
    # Test 1: All parameters are given
    cam_calibraton = create_cam_calibration(
        type="type",
        c1=1.0,
        c2=2.0,
        c3=3.0,
        c4=4.0,
        pixel_aspect_ratio=5.0,
        pos_x_m=6.0,
        pos_y_m=7.0,
        pos_z_m=8.0,
        rot_x_deg=9.0,
        rot_z1_deg=10.0,
        rot_z2_deg=11.0,
        cx_offset_px=12.0,
        cy_offset_px=13.0,
        img_height_px=14,
        img_width_px=15,
    )

    assert isinstance(cam_calibraton, CamCalibration)
    assert cam_calibraton.type == "type"
    assert cam_calibraton.intrinsics.c1 == 1.0
    assert cam_calibraton.intrinsics.c2 == 2.0
    assert cam_calibraton.intrinsics.c3 == 3.0
    assert cam_calibraton.intrinsics.c4 == 4.0
    assert cam_calibraton.intrinsics.pixel_aspect_ratio == 5.0
    assert cam_calibraton.extrinsics.pos_x_m == 6.0
    assert cam_calibraton.extrinsics.pos_y_m == 7.0
    assert cam_calibraton.extrinsics.pos_z_m == 8.0
    assert cam_calibraton.extrinsics.rot_x_deg == 9.0
    assert cam_calibraton.extrinsics.rot_z1_deg == 10.0
    assert cam_calibraton.extrinsics.rot_z2_deg == 11.0
    assert cam_calibraton.base_intrinsics.cx_offset_px == 12.0
    assert cam_calibraton.base_intrinsics.cy_offset_px == 13.0
    assert cam_calibraton.base_intrinsics.img_height_px == 14
    assert cam_calibraton.base_intrinsics.img_width_px == 15

    # Test 2: BaseIntrinsics, Extrinsics and Intrinsics are given
    cam_calibraton = create_cam_calibration(
        type="type",
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
    assert isinstance(cam_calibraton, CamCalibration)
    assert cam_calibraton.type == "type"
    assert cam_calibraton.intrinsics.c1 == 0.0
    assert cam_calibraton.intrinsics.c2 == 0.0
    assert cam_calibraton.intrinsics.c3 == 0.0
    assert cam_calibraton.intrinsics.c4 == 0.0
    assert cam_calibraton.intrinsics.pixel_aspect_ratio == 0.0
    assert cam_calibraton.extrinsics.pos_x_m == 0.0
    assert cam_calibraton.extrinsics.pos_y_m == 0.0
    assert cam_calibraton.extrinsics.pos_z_m == 0.0
    assert cam_calibraton.extrinsics.rot_x_deg == 0.0
    assert cam_calibraton.extrinsics.rot_z1_deg == 0.0
    assert cam_calibraton.extrinsics.rot_z2_deg == 0.0
    assert cam_calibraton.base_intrinsics.cx_offset_px == 0.0
    assert cam_calibraton.base_intrinsics.cy_offset_px == 0.0
    assert cam_calibraton.base_intrinsics.img_height_px == 0
    assert cam_calibraton.base_intrinsics.img_width_px == 0

    # Test 3: invalid creation

    with pytest.raises(
        ValueError,
    ):
        assert create_cam_calibration(type="type")

    with pytest.raises(ValueError, match="base_intrinsics, extrinsics and intrinsics must be all defined or all None"):
        assert create_cam_calibration(
            type="type",
            base_intrinsics=BaseIntrinsics(cx_offset_px=0.0, cy_offset_px=0.0, img_height_px=0, img_width_px=0),
        )

    with pytest.raises(
        ValueError,
        match=(
            "cx_offset_px, cy_offset_px, img_height_px, img_width_px, pos_x_m, pos_y_m, pos_z_m, rot_x_deg, "
            "rot_z1_deg, rot_z2_deg, c1, c2, c3, c4 and pixel_aspect_ratio must be all defined or all None"
        ),
    ):
        assert create_cam_calibration(type="type", c1=1.0)

    with pytest.raises(
        ValueError,
        match="base_intrinsics, extrinsics and intrinsics must defined or cx_offset_px, cy_offset_px, img_height_px, "
        "img_width_px, pos_x_m, pos_y_m, pos_z_m, rot_x_deg, rot_z1_deg, rot_z2_deg, c1, c2, c3, c4 and "
        "pixel_aspect_ratio must be defined but not both",
    ):
        assert create_cam_calibration(
            type="type",
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
            c1=1.0,
            c2=2.0,
            c3=3.0,
            c4=4.0,
            pixel_aspect_ratio=5.0,
            pos_x_m=6.0,
            pos_y_m=7.0,
            pos_z_m=8.0,
            rot_x_deg=9.0,
            rot_z1_deg=10.0,
            rot_z2_deg=11.0,
            cx_offset_px=12.0,
            cy_offset_px=13.0,
            img_height_px=14,
            img_width_px=15,
        )
