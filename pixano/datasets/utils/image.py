# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from io import BytesIO

from PIL import Image

from pixano.features.utils.image import image_to_binary


def image_to_thumbnail(image: bytes | Image.Image) -> bytes:
    """Generate image thumbnail.

    Args:
        image: Image as binary or as a Pillow Image.

    Returns:
        Image thumbnail as binary.
    """
    if isinstance(image, bytes):
        image = Image.open(BytesIO(image))

    image.thumbnail((128, 128))
    return image_to_binary(image)
