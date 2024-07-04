# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.features.schemas.image import Image, create_image, is_image
from tests.datasets.features.utils import make_tests_is_sublass_strict


ASSETS_DIRECTORY = Path(__file__).parent.parent.parent.parent / "assets"
IMAGE_ASSET_URL = ASSETS_DIRECTORY / "sample_data/image_jpg.jpg"


class TestImage:
    def test_open(self):
        image = create_image(
            item_id="item_id",
            url=IMAGE_ASSET_URL,
            other_path=ASSETS_DIRECTORY,
        )

        io = image.open(ASSETS_DIRECTORY)
        assert isinstance(io, str)

    def test_open_url(self):
        image = Image.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY)
        assert isinstance(image, str)


def test_is_image():
    make_tests_is_sublass_strict(is_image, Image)


def test_create_image():
    # Test 1: read url
    image: Image = create_image(
        item_id="item_id",
        url=IMAGE_ASSET_URL,
    )

    assert isinstance(image, Image)
    assert isinstance(image.id, str)
    assert image.item_id == "item_id"
    assert image.url == str(IMAGE_ASSET_URL.as_posix())
    assert image.width == 586
    assert image.height == 640
    assert image.format == "JPEG"

    # Test 2: read url with custom id and other path
    image = create_image(item_id="item_id", id="id", url=IMAGE_ASSET_URL, other_path=ASSETS_DIRECTORY)

    assert isinstance(image, Image)
    assert image.id == "id"
    assert image.item_id == "item_id"
    assert image.url == "sample_data/image_jpg.jpg"
    assert image.width == 586
    assert image.height == 640
    assert image.format == "JPEG"

    # Test 3: no read
    image = create_image(item_id="item_id", url=IMAGE_ASSET_URL, id="id", width=100, height=100, format="PNG")

    assert isinstance(image, Image)
    assert image.id == "id"
    assert image.item_id == "item_id"
    assert image.url == str(IMAGE_ASSET_URL.as_posix())
    assert image.width == 100
    assert image.height == 100
    assert image.format == "PNG"
