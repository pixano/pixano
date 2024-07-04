# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.types.keypoints import KeyPoints, create_keypoints, is_keypoints, map_back2front_vertices
from tests.datasets.features.utils import make_tests_is_sublass_strict


class TestKeyPoints:
    def test_none(self):
        none_keypoints = KeyPoints.none()
        assert none_keypoints.template_id == "N/A"
        assert none_keypoints.coords == [0, 0]
        assert none_keypoints.states == ["invisible"]


def test_is_keypoints():
    make_tests_is_sublass_strict(is_keypoints, KeyPoints)


def test_create_keypoints():
    keypoints = create_keypoints(template_id="template_id", coords=[1, 1], states=["visible"])
    assert isinstance(keypoints, KeyPoints)
    assert keypoints.template_id == "template_id"
    assert keypoints.coords == [1, 1]
    assert keypoints.states == ["visible"]


def test_map_back2front_vertices():
    keypoints = KeyPoints(template_id="template_id", coords=[1, 2, 3, 4], states=["visible", "invisible"])
    expected_result = [
        {"x": 1, "y": 2, "features": {"state": "visible"}},
        {"x": 3, "y": 4, "features": {"state": "invisible"}},
    ]
    assert map_back2front_vertices(keypoints) == expected_result
