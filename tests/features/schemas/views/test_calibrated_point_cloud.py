# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import CalibratedPointCloud


def test_calibrated_point_cloud():
    # Test: Create a CalibratedPointCloud instance with all required fields
    calibrated_point_cloud = CalibratedPointCloud(
        record_id="record_id",
        logical_name="lidar",
        uri="/home/mfauvel/Datasets/NuScenes/samples/LIDAR_TOP/n008-2018-05-21-11-06-59-0400__LIDAR_TOP__1526915243012465.ply",
        extrinsic_matrix=[1.0] * 16,
        ego_to_world=[1.0] * 16,
    )

    assert (
        calibrated_point_cloud.uri
        == "/home/mfauvel/Datasets/NuScenes/samples/LIDAR_TOP/n008-2018-05-21-11-06-59-0400__LIDAR_TOP__1526915243012465.ply"
    )
    assert calibrated_point_cloud.record_id == "record_id"
    assert calibrated_point_cloud.logical_name == "lidar"
    assert calibrated_point_cloud.extrinsic_matrix == [1.0] * 16
    assert calibrated_point_cloud.ego_to_world == [1.0] * 16
    print("test_calibrated_point_cloud passed.")
