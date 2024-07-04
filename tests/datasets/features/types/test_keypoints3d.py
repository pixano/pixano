# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.types.keypoints3d import KeyPoints3D, create_keypoints3d, is_keypoints3d
from tests.datasets.features.utils import make_tests_is_sublass_strict


class TestKeyPoints3D:
    def test_none(self):
        none_keypoints = KeyPoints3D.none()
        assert none_keypoints.template_id == "N/A"
        assert none_keypoints.coords == [0, 0, 0]
        assert none_keypoints.states == ["visible"]


def test_is_keypoints3d():
    make_tests_is_sublass_strict(is_keypoints3d, KeyPoints3D)


def test_create_keypoints3d():
    keypoints = create_keypoints3d(template_id="template_id", coords=[1, 1, 1], states=["visible"])
    assert isinstance(keypoints, KeyPoints3D)
    assert keypoints.template_id == "template_id"
    assert keypoints.coords == [1, 1, 1]
    assert keypoints.states == ["visible"]
