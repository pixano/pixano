# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile

import cv2
import numpy as np
import pytest
from PIL import Image

from pixano.datasets.utils.image import (
    binary_to_url,
    depth_array_to_gray,
    depth_file_to_binary,
    encode_rle,
    image_to_binary,
    image_to_thumbnail,
    mask_to_polygons,
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)


def test_binary_to_url():
    binary = b"binary"
    url = binary_to_url(binary)
    assert url == "data:image;base64,YmluYXJ5"


def test_depth_array_to_gray():
    input = np.array([[0.2, 0.4], [0.6, 0.8]])
    output = depth_array_to_gray(input)
    expected_output = np.array([[[135, 8, 13], [135, 8, 13]], [[135, 8, 13], [135, 8, 13]]])

    assert np.array_equal(output, expected_output)


def test_depth_file_to_binary():
    depth_path = tempfile.NamedTemporaryFile(suffix=".png")
    input = np.array([[0.2, 0.4], [0.6, 0.8]])
    cv2.imwrite(depth_path.name, input)
    binary = depth_file_to_binary(depth_path.name)
    assert isinstance(binary, bytes)


@pytest.mark.skip("Not implemented")
def test_encode_rle():
    pass


def test_image_to_binary():
    input = Image.new("RGB", (100, 100))
    binary = image_to_binary(input)
    assert isinstance(binary, bytes)


def test_image_to_thumbnail():
    input = Image.new("RGB", (100, 100))
    binary = image_to_thumbnail(input)
    assert isinstance(binary, bytes)


@pytest.mark.skip("Not implemented")
def test_mask_to_polygons():
    pass


@pytest.mark.skip("Not implemented")
def test_mask_to_rle():
    pass


@pytest.mark.skip("Not implemented")
def test_polygons_to_rle():
    pass


@pytest.mark.skip("Not implemented")
def test_rle_to_mask():
    pass


@pytest.mark.skip("Not implemented")
def test_rle_to_polygons():
    pass


@pytest.mark.skip("Not implemented")
def test_rle_to_urle():
    pass


@pytest.mark.skip("Not implemented")
def test_urle_to_rle():
    pass
