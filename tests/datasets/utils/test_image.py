# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from PIL import Image

from pixano.datasets.utils.image import (
    image_to_thumbnail,
)


def test_image_to_thumbnail():
    input = Image.new("RGB", (100, 100))
    binary = image_to_thumbnail(input)
    assert isinstance(binary, bytes)
