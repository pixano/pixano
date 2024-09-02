# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import (
    KeyPoints,
    KeyPoints3D,
    create_keypoints,
    create_keypoints3d,
    is_keypoints,
    is_keypoints3d,
)
from pixano.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


class TestKeyPoints:
    def test_none(self):
        none_keypoints = KeyPoints.none()
        assert none_keypoints.template_id == ""
        assert none_keypoints.coords == [0, 0]
        assert none_keypoints.states == ["invisible"]


class TestKeyPoints3D:
    def test_none(self):
        none_keypoints = KeyPoints3D.none()
        assert none_keypoints.template_id == ""
        assert none_keypoints.coords == [0, 0, 0]
        assert none_keypoints.states == ["visible"]


def test_is_keypoints():
    make_tests_is_sublass_strict(is_keypoints, KeyPoints)


def test_is_keypoints3d():
    make_tests_is_sublass_strict(is_keypoints3d, KeyPoints3D)


def test_create_keypoints():
    # Test 1: default references
    keypoints = create_keypoints(template_id="template_id", coords=[1, 1], states=["visible"])
    assert isinstance(keypoints, KeyPoints)
    assert keypoints.template_id == "template_id"
    assert keypoints.coords == [1, 1]
    assert keypoints.states == ["visible"]
    assert keypoints.id == ""
    assert keypoints.item_ref == ItemRef.none()
    assert keypoints.view_ref == ViewRef.none()
    assert keypoints.entity_ref == EntityRef.none()

    # Test 2: custom references
    keypoints = create_keypoints(
        id="id",
        item_ref=ItemRef(id="item_id"),
        view_ref=ViewRef(id="view_id", name="view"),
        entity_ref=EntityRef(id="entity_id", name="entity"),
        template_id="template_id",
        coords=[1, 1],
        states=["visible"],
    )

    assert isinstance(keypoints, KeyPoints)
    assert keypoints.template_id == "template_id"
    assert keypoints.coords == [1, 1]
    assert keypoints.states == ["visible"]
    assert keypoints.id == "id"
    assert keypoints.item_ref == ItemRef(id="item_id")
    assert keypoints.view_ref == ViewRef(id="view_id", name="view")
    assert keypoints.entity_ref == EntityRef(id="entity_id", name="entity")


def test_create_keypoints3d():
    # Test 1: default references
    keypoints = create_keypoints3d(template_id="template_id", coords=[1, 1, 1], states=["visible"])
    assert isinstance(keypoints, KeyPoints3D)
    assert keypoints.template_id == "template_id"
    assert keypoints.coords == [1, 1, 1]
    assert keypoints.states == ["visible"]
    assert keypoints.id == ""
    assert keypoints.item_ref == ItemRef.none()
    assert keypoints.view_ref == ViewRef.none()
    assert keypoints.entity_ref == EntityRef.none()

    # Test 2: custom references
    keypoints = create_keypoints3d(
        id="id",
        item_ref=ItemRef(id="item_id"),
        view_ref=ViewRef(id="view_id", name="view"),
        entity_ref=EntityRef(id="entity_id", name="entity"),
        template_id="template_id",
        coords=[1, 1, 1],
        states=["visible"],
    )

    assert isinstance(keypoints, KeyPoints3D)
    assert keypoints.template_id == "template_id"
    assert keypoints.coords == [1, 1, 1]
    assert keypoints.states == ["visible"]
    assert keypoints.id == "id"
    assert keypoints.item_ref == ItemRef(id="item_id")
    assert keypoints.view_ref == ViewRef(id="view_id", name="view")
    assert keypoints.entity_ref == EntityRef(id="entity_id", name="entity")


def test_map_back2front_vertices():
    keypoints = KeyPoints(template_id="template_id", coords=[1, 2, 3, 4], states=["visible", "invisible"])
    expected_result = [
        {"x": 1, "y": 2, "features": {"state": "visible"}},
        {"x": 3, "y": 4, "features": {"state": "invisible"}},
    ]
    assert keypoints.map_back2front_vertices() == expected_result
