# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features import PointCloud, create_point_cloud, is_point_cloud
from pixano.datasets.features.types.schema_reference import ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_point_cloud():
    make_tests_is_sublass_strict(is_point_cloud, PointCloud)


def test_create_point_cloud():
    # Test 1: Default values
    point_cloud = create_point_cloud(
        url="sample_data/point_cloud_ply.ply",
    )

    assert point_cloud == PointCloud(
        url="sample_data/point_cloud_ply.ply",
        id="",
        item=ItemRef.none(),
        parent_ref=ViewRef.none(),
    )

    # Test 2: Custom values
    point_cloud = create_point_cloud(
        url="sample_data/point_cloud_ply.ply",
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    assert point_cloud == PointCloud(
        url="sample_data/point_cloud_ply.ply",
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
