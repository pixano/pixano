# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.point_cloud import PointCloud, create_point_cloud, is_point_cloud
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_point_cloud():
    make_tests_is_sublass_strict(is_point_cloud, PointCloud)


def test_create_point_cloud():
    # Test 1: Default values
    point_cloud = create_point_cloud(
        item_id="item_id",
        url="sample_data/point_cloud_ply.ply",
    )

    assert isinstance(point_cloud, PointCloud)
    assert point_cloud.item_id == "item_id"
    assert point_cloud.url == "sample_data/point_cloud_ply.ply"
    assert isinstance(point_cloud.id, str)

    # Test 2: Custom values
    point_cloud = create_point_cloud(
        item_id="item_id",
        id="id",
        url="sample_data/point_cloud_ply.ply",
    )

    assert isinstance(point_cloud, PointCloud)
    assert point_cloud.item_id == "item_id"
    assert point_cloud.id == "id"
    assert point_cloud.url == "sample_data/point_cloud_ply.ply"
