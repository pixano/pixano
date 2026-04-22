# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import CalibratedImage


def test_calibrated_image():
    # Test: Create a CalibratedImage instance from a uri with all required fields
    calibrated_image = CalibratedImage.from_uri(
        record_id="record_id",
        logical_name="front_camera",
        uri="/path/to/image.jpg",
        f=(1000.0, 1000.0),
        c=(640.0, 480.0),
        distortion=[0.1, 0.01, 0.001],
        extrinsic_matrix=[1.0] * 16,
        ego_to_world=[1.0] * 16,
    )

    assert calibrated_image.uri == "/path/to/image.jpg"
    assert calibrated_image.record_id == "record_id"
    assert calibrated_image.logical_name == "front_camera"
    assert calibrated_image.f == (1000.0, 1000.0)
    assert calibrated_image.c == (640.0, 480.0)
    assert calibrated_image.distortion == [0.1, 0.01, 0.001]
    assert calibrated_image.extrinsic_matrix == [1.0] * 16
    assert calibrated_image.ego_to_world == [1.0] * 16
    print("test_calibrated_image passed.")
