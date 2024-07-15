# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np
import pytest

from pixano.datasets.features import BBox, BBox3D, CompressedRLE, create_bbox, create_bbox3d, is_bbox, is_bbox3d
from pixano.datasets.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


class TestBBox:
    def test_format(self, bbox_xyxy, bbox_xywh):
        assert bbox_xyxy.format == "xyxy"
        assert bbox_xywh.format == "xywh"

    def test_none(self):
        none_bbox = BBox.none()

        assert none_bbox.id == ""
        assert none_bbox.item_ref == ItemRef.none()
        assert none_bbox.view_ref == ViewRef.none()
        assert none_bbox.entity_ref == EntityRef.none()
        assert none_bbox.confidence == -1
        assert none_bbox.is_normalized
        assert none_bbox.format == "xywh"
        assert np.allclose(none_bbox.xywh_coords, [0, 0, 0, 0])

    def test_is_normalized(self, bbox_xyxy, bbox_xywh):
        assert not bbox_xyxy.is_normalized
        assert not bbox_xywh.is_normalized

    def test_xyxy_coords(self, bbox_xywh, coords):
        converted_coords = bbox_xywh.xyxy_coords

        assert np.allclose(converted_coords, coords["xyxy"])

    def test_xywh_coords(self, bbox_xyxy, coords):
        converted_coords = bbox_xyxy.xywh_coords

        assert np.allclose(converted_coords, coords["xywh"])

    def test_format_conversion(self, bbox_xyxy, bbox_xywh, coords):
        converted_xywh_bbox = bbox_xyxy.to_xywh()

        assert converted_xywh_bbox.format == "xywh"
        assert np.allclose(converted_xywh_bbox.xywh_coords, coords["xywh"])

        converted_xyxy_bbox = bbox_xywh.to_xyxy()

        assert converted_xyxy_bbox.format == "xyxy"
        assert np.allclose(converted_xyxy_bbox.xyxy_coords, coords["xyxy"])

    def test_normalization(self, bbox_xyxy, coords, height_width):
        height, width = height_width
        normalized_bbox = bbox_xyxy.normalize(height, width)

        assert np.allclose(normalized_bbox.xyxy_coords, coords["normalized_xyxy"])

        denormalized_bbox = normalized_bbox.denormalize(height, width)

        assert np.allclose(denormalized_bbox.xyxy_coords, coords["xyxy"])

    @pytest.mark.parametrize(
        "id, item_ref, view_ref, entity_ref",
        [
            (
                "bbox_1",
                ItemRef(id="item_1"),
                ViewRef(id="view_1", name="view"),
                EntityRef(id="entity_1", name="entity"),
            ),
            ("", ItemRef.none(), ViewRef.none(), EntityRef.none()),
        ],
    )
    def test_from_xyxy(self, coords, id, item_ref, view_ref, entity_ref):
        bbox = BBox.from_xyxy(
            coords["xyxy"],
            confidence=0.5,
            is_normalized=False,
            id=id,
            item_ref=item_ref,
            view_ref=view_ref,
            entity_ref=entity_ref,
        )

        assert bbox.confidence == 0.5
        assert np.allclose(bbox.xyxy_coords, coords["xyxy"])
        assert not bbox.is_normalized
        assert id == id
        assert bbox.item_ref == item_ref
        assert bbox.view_ref == view_ref
        assert bbox.entity_ref == entity_ref

    @pytest.mark.parametrize(
        "id, item_ref, view_ref, entity_ref",
        [
            (
                "bbox_1",
                ItemRef(id="item_1"),
                ViewRef(id="view_1", name="view"),
                EntityRef(id="entity_1", name="entity"),
            ),
            ("", ItemRef.none(), ViewRef.none(), EntityRef.none()),
        ],
    )
    def test_from_xywh(self, coords, id, item_ref, view_ref, entity_ref):
        bbox = BBox.from_xywh(
            coords["xywh"],
            confidence=-1,
            is_normalized=False,
            id=id,
            item_ref=item_ref,
            view_ref=view_ref,
            entity_ref=entity_ref,
        )

        assert bbox.confidence == -1
        assert np.allclose(bbox.xywh_coords, coords["xywh"])
        assert not bbox.is_normalized
        assert id == id
        assert bbox.item_ref == item_ref
        assert bbox.view_ref == view_ref
        assert bbox.entity_ref == entity_ref

    @pytest.mark.parametrize(
        "id, item_ref, view_ref, entity_ref",
        [
            (
                "bbox_1",
                ItemRef(id="item_1"),
                ViewRef(id="view_1", name="view"),
                EntityRef(id="entity_1", name="entity"),
            ),
            ("", ItemRef.none(), ViewRef.none(), EntityRef.none()),
        ],
    )
    def test_from_mask(self, id, item_ref, view_ref, entity_ref):
        mask = np.ones((10, 10), dtype=bool)
        bbox = BBox.from_mask(mask, id=id, item_ref=item_ref, view_ref=view_ref, entity_ref=entity_ref)

        assert np.allclose(bbox.xywh_coords, [0, 0, 1.0, 1.0])
        assert bbox.is_normalized
        assert bbox.confidence == -1
        assert bbox.id == id
        assert bbox.item_ref == item_ref
        assert bbox.view_ref == view_ref
        assert bbox.entity_ref == entity_ref

    @pytest.mark.parametrize(
        "id, item_ref, view_ref, entity_ref",
        [
            (
                "bbox_1",
                ItemRef(id="item_1"),
                ViewRef(id="view_1", name="view"),
                EntityRef(id="entity_1", name="entity"),
            ),
            ("", ItemRef.none(), ViewRef.none(), EntityRef.none()),
        ],
    )
    def test_from_rle(self, id, item_ref, view_ref, entity_ref):
        rle = CompressedRLE.from_mask(np.ones((10, 10), dtype=bool))
        bbox = BBox.from_rle(rle, id=id, item_ref=item_ref, view_ref=view_ref, entity_ref=entity_ref)

        assert np.allclose(bbox.xywh_coords, [0, 0, 1.0, 1.0])
        assert bbox.is_normalized
        assert bbox.confidence == -1
        assert bbox.id == id
        assert bbox.item_ref == item_ref
        assert bbox.view_ref == view_ref
        assert bbox.entity_ref == entity_ref


def test_is_bbox():
    make_tests_is_sublass_strict(is_bbox, BBox)


def test_is_bbox3d():
    make_tests_is_sublass_strict(is_bbox3d, BBox3D)


def test_create_bbox():
    # Test 1: default references
    bbox = create_bbox([1, 1, 2, 2], "xyxy", False, 0.5)
    assert isinstance(bbox, BBox)
    assert bbox.format == "xyxy"
    assert not bbox.is_normalized
    assert bbox.confidence == 0.5
    assert bbox.xyxy_coords == [1, 1, 2, 2]
    assert bbox.id == ""
    assert bbox.item_ref == ItemRef.none()
    assert bbox.view_ref == ViewRef.none()
    assert bbox.entity_ref == EntityRef.none()

    # Test 2: with references
    bbox = create_bbox(
        [0.1, 0.1, 0.2, 0.2],
        "xyxy",
        True,
        0.5,
        id="bbox_1",
        item_ref=ItemRef(id="item_1"),
        view_ref=ViewRef(id="view_1", name="view"),
        entity_ref=EntityRef(id="entity_1", name="entity"),
    )
    assert isinstance(bbox, BBox)
    assert bbox.format == "xyxy"
    assert bbox.is_normalized
    assert bbox.confidence == 0.5
    assert bbox.xyxy_coords == [0.1, 0.1, 0.2, 0.2]
    assert bbox.id == "bbox_1"
    assert bbox.item_ref == ItemRef(id="item_1")
    assert bbox.view_ref == ViewRef(id="view_1", name="view")
    assert bbox.entity_ref == EntityRef(id="entity_1", name="entity")


def test_create_bbox3d():
    # Test 1: default references
    bbox = create_bbox3d(coords=[1, 1, 1, 2, 2, 2], format="xyzwhd", heading=[3.0], is_normalized=False)
    assert isinstance(bbox, BBox3D)
    assert bbox.coords == [1, 1, 1, 2, 2, 2]
    assert bbox.format == "xyzwhd"
    assert bbox.heading == [3.0]
    assert bbox.confidence == -1
    assert not bbox.is_normalized
    assert bbox.id == ""
    assert bbox.item_ref == ItemRef.none()
    assert bbox.view_ref == ViewRef.none()
    assert bbox.entity_ref == EntityRef.none()

    # Test 2: with references
    bbox = create_bbox3d(
        coords=[0.1, 0.1, 0.1, 0.2, 0.2, 0.2],
        format="xyzwhd",
        heading=[3.0],
        is_normalized=True,
        confidence=0.5,
        id="bbox_1",
        item_ref=ItemRef(id="item_1"),
        view_ref=ViewRef(id="view_1", name="view"),
        entity_ref=EntityRef(id="entity_1", name="entity"),
    )
    assert isinstance(bbox, BBox3D)
    assert bbox.coords == [0.1, 0.1, 0.1, 0.2, 0.2, 0.2]
    assert bbox.format == "xyzwhd"
    assert bbox.heading == [3.0]
    assert bbox.confidence == 0.5
    assert bbox.is_normalized
    assert bbox.id == "bbox_1"
    assert bbox.item_ref == ItemRef(id="item_1")
    assert bbox.view_ref == ViewRef(id="view_1", name="view")
    assert bbox.entity_ref == EntityRef(id="entity_1", name="entity")
