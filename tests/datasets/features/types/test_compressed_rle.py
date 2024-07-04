# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np
import pytest

from pixano.datasets.features import CompressedRLE
from pixano.datasets.features.types.compressed_rle import create_compressed_rle, is_compressed_rle
from pixano.datasets.utils import (
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)
from pixano.datasets.utils.image import encode_rle
from tests.datasets.features.utils import make_tests_is_sublass_strict


@pytest.fixture()
def size():
    return [10, 10]


@pytest.fixture()
def counts():
    return bytes(b";37000k1")


@pytest.fixture()
def rle(size, counts):
    return CompressedRLE(size=size, counts=counts)


class TestCompressedRLE:
    def test_none(self):
        none_rle = CompressedRLE.none()
        assert none_rle.size == [0.0, 0.0]
        assert none_rle.counts == b""

    def test_to_mask(self, rle):
        mask = rle.to_mask()
        expected_mask = rle_to_mask(rle.model_dump())

        assert isinstance(mask, np.ndarray)
        assert mask.tolist() == expected_mask.tolist()

    def test_to_urle(self, rle):
        urle = rle.to_urle()
        expected_urle = rle_to_urle(rle.model_dump())

        assert urle == expected_urle

    def test_to_polygons(self, rle):
        polygons = rle.to_polygons()
        expected_polygons = rle_to_polygons(rle.model_dump())

        assert polygons == expected_polygons

    def test_from_mask(self):
        mask = np.ndarray((10, 10), dtype=bool)
        rle = CompressedRLE.from_mask(mask)
        expected_rle_dict = mask_to_rle(mask)
        expected_rle = CompressedRLE(**expected_rle_dict)

        assert rle.size == expected_rle.size
        assert rle.counts == expected_rle.counts

    def test_from_urle(self):
        urle = {"counts": [1, 2, 3, 2, 4, 1], "size": [10, 10]}
        rle = CompressedRLE.from_urle(urle)
        expected_rle_dict = urle_to_rle(urle)
        expected_rle = CompressedRLE(**expected_rle_dict)

        assert rle.size == expected_rle.size
        assert rle.counts == expected_rle.counts

    def test_from_polygons(self):
        polygons = [[1, 1, 2, 2, 2, 1], [3, 3, 4, 4, 4, 3]]
        height, width = 10, 10
        rle = CompressedRLE.from_polygons(polygons, height, width)
        expected_rle_dict = polygons_to_rle(polygons, height, width)
        expected_rle = CompressedRLE(**expected_rle_dict)

        assert rle.size == expected_rle.size
        assert rle.counts == expected_rle.counts

    def test_encode(self):
        mask = np.ndarray((10, 10), dtype=bool).tolist()
        rle = CompressedRLE.encode(mask, 10, 10)
        expected_rle_dict = encode_rle(mask, 10, 10)
        expected_rle = CompressedRLE(**expected_rle_dict)

        assert rle.size == expected_rle.size
        assert rle.counts == expected_rle.counts


def test_is_compressed_rle():
    make_tests_is_sublass_strict(is_compressed_rle, CompressedRLE)


def test_create_compressed_rle(size, counts):
    rle = create_compressed_rle(size, counts)

    assert isinstance(rle, CompressedRLE)
    assert rle.size == size
    assert rle.counts == counts
