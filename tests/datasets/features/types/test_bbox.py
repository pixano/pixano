# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np
import pytest

from pixano.datasets.features.types import BBox
from pixano.datasets.features.types.bbox import create_bbox, is_bbox
from pixano.datasets.features.types.compressed_rle import CompressedRLE
from tests.datasets.features.utils import make_tests_is_sublass_strict


@pytest.fixture()
def height_width():
    return 4, 6


@pytest.fixture()
def coords():
    return {
        "xyxy": [1, 1, 3, 3],
        "xywh": [1, 1, 2, 2],
        "normalized_xyxy": [1 / 6, 1 / 4, 3 / 6, 3 / 4],
        "normalized_xywh": [1 / 6, 1 / 4, 2 / 6, 2 / 4],
    }


@pytest.fixture()
def bbox_xyxy(coords):
    return BBox.from_xyxy(coords["xyxy"], confidence=0.5, is_normalized=False)


@pytest.fixture()
def bbox_xywh(coords):
    return BBox.from_xywh(coords["xywh"], confidence=0.0, is_normalized=False)


class TestBBox:
    def test_format(self, bbox_xyxy, bbox_xywh):
        assert bbox_xyxy.format == "xyxy"
        assert bbox_xywh.format == "xywh"

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

    def test_from_xyxy(self, coords):
        bbox = BBox.from_xyxy(coords["xyxy"], confidence=0.5, is_normalized=False)

        assert bbox.confidence == 0.5
        assert np.allclose(bbox.xyxy_coords, coords["xyxy"])
        assert not bbox.is_normalized

    def test_from_xywh(self, coords):
        bbox = BBox.from_xywh(coords["xywh"], confidence=-1, is_normalized=False)

        assert bbox.confidence == -1
        assert np.allclose(bbox.xywh_coords, coords["xywh"])
        assert not bbox.is_normalized

    def test_from_mask(self):
        mask = np.ones((10, 10), dtype=bool)
        bbox = BBox.from_mask(mask)

        assert np.allclose(bbox.xywh_coords, [0, 0, 1.0, 1.0])
        assert bbox.is_normalized
        assert bbox.confidence == -1

    def test_from_rle(self):
        rle = CompressedRLE.from_mask(np.ones((10, 10), dtype=bool))
        bbox = BBox.from_rle(rle)

        assert np.allclose(bbox.xywh_coords, [0, 0, 1.0, 1.0])
        assert bbox.is_normalized
        assert bbox.confidence == -1


def test_is_bbox():
    make_tests_is_sublass_strict(is_bbox, BBox)


def test_create_bbox():
    bbox = create_bbox([1, 1, 2, 2], "xyxy", False, 0.5)
    assert isinstance(bbox, BBox)
    assert bbox.format == "xyxy"
    assert not bbox.is_normalized
    assert bbox.confidence == 0.5
    assert bbox.xyxy_coords == [1, 1, 2, 2]
