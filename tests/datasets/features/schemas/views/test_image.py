# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.features import Image, create_image, is_image
from pixano.datasets.features.types.schema_reference import ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


ASSETS_DIRECTORY = Path(__file__).parent.parent.parent.parent.parent / "assets"
IMAGE_ASSET_URL = ASSETS_DIRECTORY / "sample_data/image_jpg.jpg"


class TestImage:
    def test_open(self):
        image = create_image(
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
    # Test 1: read url and default references
    image: Image = create_image(
        url=IMAGE_ASSET_URL,
    )

    assert image == Image(
        url=str(IMAGE_ASSET_URL.as_posix()),
        width=586,
        height=640,
        format="JPEG",
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    )

    # Test 2: read url with custom id and other path and custom references
    image = create_image(
        url=IMAGE_ASSET_URL,
        other_path=ASSETS_DIRECTORY,
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    assert image == Image(
        url="sample_data/image_jpg.jpg",
        width=586,
        height=640,
        format="JPEG",
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    # Test 3: no read
    image = create_image(url=IMAGE_ASSET_URL, width=100, height=100, format="PNG")
    assert image == Image(
        url=str(IMAGE_ASSET_URL.as_posix()),
        width=100,
        height=100,
        format="PNG",
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    )

