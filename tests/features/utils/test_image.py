# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile

import cv2
import numpy as np
import PIL.Image
import pytest
from PIL.Image import Image as PILImage

from pixano.features.schemas.views.image import Image
from pixano.features.utils.image import (
    base64_to_image,
    binary_to_url,
    depth_array_to_gray,
    depth_file_to_binary,
    encode_rle,
    get_image_thumbnail,
    image_to_base64,
    image_to_binary,
    mask_to_polygons,
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY


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
    input = PIL.Image.new("RGB", (100, 100))
    binary = image_to_binary(input)
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


def test_image_to_base64():
    image = Image.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY, "image")
    base64_image = image_to_base64(image)
    assert isinstance(base64_image, str)
    assert base64_image.startswith("data:image/jpeg;base64,")


def test_base64_to_image():
    image = Image.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY, "image")
    base64_image = image_to_base64(image)
    converted_image = base64_to_image(base64_image)
    assert isinstance(converted_image, PILImage)
    assert image.format == converted_image.format
    assert image.size == converted_image.size


def test_get_image_thumbnail():
    image = Image.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY, "image")
    image_thumbnail = get_image_thumbnail(image, (100, 100))
    assert isinstance(image_thumbnail, PILImage)
    assert image_thumbnail.size == (92, 100)

    for size in [(0, 0), (100, 0), (0, 100), "yolo", (0.1, 2)]:
        match_regex = "Invalid thumbnail size: " + str(size)
        with pytest.raises(ValueError, match=r"".format(match_regex)):  # noqa: F523
            get_image_thumbnail(image, size)
