# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.types.bbox3d import BBox3D, create_bbox3d, is_bbox3d
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_bbox3d():
    make_tests_is_sublass_strict(is_bbox3d, BBox3D)


def test_create_bbox3d():
    bbox = create_bbox3d(position=[1, 1, 1, 2, 2, 2], size=[1, 1, 1], heading=3.0)
    assert isinstance(bbox, BBox3D)
    assert bbox.position == [1, 1, 1, 2, 2, 2]
    assert bbox.size == [1, 1, 1]
    assert bbox.heading == 3.0
