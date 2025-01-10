# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from PIL.Image import Image as PILImage

from pixano.features import Image, create_image, is_image
from pixano.features.types.schema_reference import ItemRef, ViewRef
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY, IMAGE_JPG_ASSET_URL, IMAGE_JPG_METADATA
from tests.features.utils import make_tests_is_sublass_strict


class TestImage:
    def test_open(self):
        image = create_image(
            url=IMAGE_JPG_ASSET_URL,
            url_relative_path=ASSETS_DIRECTORY,
        )

        base64_image = image.open(ASSETS_DIRECTORY)
        assert isinstance(base64_image, str)
        assert base64_image.startswith("data:image/jpeg;base64,")

        pil = image.open(ASSETS_DIRECTORY, output_type="image")
        assert pil.format == "JPEG"

    def test_open_url(self):
        image = Image.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY, "image")
        assert isinstance(image, PILImage)
        assert image.format == "JPEG"

        base64_image = Image.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY)
        assert isinstance(base64_image, str)
        assert base64_image.startswith("data:image/jpeg;base64,")

        with pytest.raises(ValueError, match=r"Invalid output type: wrong_type"):
            Image.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY, output_type="wrong_type")

    def test_shorten_url_to_relative_path(self):
        image = create_image(
            url=IMAGE_JPG_ASSET_URL,
            url_relative_path=ASSETS_DIRECTORY,
        )
        base64_image = image.open(ASSETS_DIRECTORY)

        image2 = create_image(url=IMAGE_JPG_ASSET_URL)
        image2.shorten_url_to_relative_path(ASSETS_DIRECTORY)
        base64_image2 = image2.open(media_dir=ASSETS_DIRECTORY)

        assert image2.url == image.url
        assert base64_image2 == base64_image
        assert image2.width == image.width
        assert image2.height == image.height
        assert image2.format == image.format


def test_is_image():
    make_tests_is_sublass_strict(is_image, Image)


def test_create_image():
    # Test 1: read url and default references
    image: Image = create_image(
        url=IMAGE_JPG_ASSET_URL,
    )

    assert image.model_dump(exclude_timestamps=True) == Image(
        url=str(IMAGE_JPG_ASSET_URL.as_posix()),
        width=IMAGE_JPG_METADATA["width"],
        height=IMAGE_JPG_METADATA["height"],
        format=IMAGE_JPG_METADATA["format"],
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    ).model_dump(exclude_timestamps=True)

    # Test 2: read url with custom id and other path and custom references
    image = create_image(
        url=IMAGE_JPG_ASSET_URL,
        url_relative_path=ASSETS_DIRECTORY,
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    assert image.model_dump(exclude_timestamps=True) == Image(
        url="sample_data/image_jpg.jpg",
        width=IMAGE_JPG_METADATA["width"],
        height=IMAGE_JPG_METADATA["height"],
        format=IMAGE_JPG_METADATA["format"],
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    ).model_dump(exclude_timestamps=True)
    # Test 3: no read
    image = create_image(url=IMAGE_JPG_ASSET_URL, width=100, height=100, format="PNG")
    assert image.model_dump(exclude_timestamps=True) == Image(
        url=str(IMAGE_JPG_ASSET_URL.as_posix()),
        width=100,
        height=100,
        format="PNG",
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    ).model_dump(exclude_timestamps=True)
