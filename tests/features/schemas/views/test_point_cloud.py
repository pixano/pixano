# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import PointCloud, create_point_cloud, is_point_cloud
from tests.features.utils import make_tests_is_sublass_strict


def test_is_point_cloud():
    make_tests_is_sublass_strict(is_point_cloud, PointCloud)


def test_create_point_cloud():
    # Test 1: Default values
    point_cloud = create_point_cloud(
        uri="sample_data/point_cloud_ply.ply",
    )

    assert point_cloud.model_dump(exclude={"created_at", "updated_at"}) == PointCloud(
        uri="sample_data/point_cloud_ply.ply",
        id="",
        record_id="",
    ).model_dump(exclude={"created_at", "updated_at"})

    # Test 2: Custom values
    point_cloud = create_point_cloud(
        uri="sample_data/point_cloud_ply.ply",
        id="id",
        record_id="record_id",
        logical_name="lidar",
    )
    assert point_cloud.model_dump(exclude={"created_at", "updated_at"}) == PointCloud(
        uri="sample_data/point_cloud_ply.ply",
        id="id",
        record_id="record_id",
        logical_name="lidar",
    ).model_dump(exclude={"created_at", "updated_at"})
