# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
import io
from io import BytesIO
from itertools import groupby

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pycocotools import mask as mask_api


def image_to_binary(image: Image.Image, im_format: str = "PNG") -> bytes:
    """Encode an image from Pillow to binary.

    Args:
        image: Pillow image.
        im_format: Image file extension.

    Returns:
        Image as binary.
    """
    with BytesIO() as output_bytes:
        image.save(output_bytes, im_format)
        im_bytes = output_bytes.getvalue()

    return im_bytes


def binary_to_url(im_bytes: bytes) -> str:
    """Encode image from binary to base 64 URL.

    Args:
        im_bytes: Image as binary.

    Returns:
        Image base 64 URL.
    """
    encoded = base64.b64encode(im_bytes).decode("utf-8")
    return f"data:image;base64,{encoded}"


def depth_file_to_binary(depth_path: str) -> bytes:
    """Encode depth file to RGB image in binary.

    Args:
        depth_path: Depth file path.

    Returns:
        Depth file as RGB image in binary.
    """
    depth = cv2.imread(depth_path, cv2.IMREAD_ANYDEPTH).astype(np.float32)
    depth = depth_array_to_gray(depth)
    depth_rgb = Image.fromarray(depth)

    return image_to_binary(depth_rgb)


def depth_array_to_gray(
    depth: np.ndarray,
    valid_start: float = 0.2,
    valid_end: float = 1,
    scale: float = 1.0,
) -> np.ndarray:
    """Encode depth array to gray levels.

    Args:
        depth: Depth array
        valid_start: Valid start.
        valid_end: Valid end.
        scale: Scale.

    Returns:
        Depth array in gray levels.
    """
    mask = depth > 1

    # Scale gives depth in mm
    depth_n = depth * scale * 0.001

    if mask.sum() > 0:
        depth_n[mask] -= depth_n[mask].min()
        depth_n[mask] /= depth_n[mask].max() / (valid_end - valid_start)
        depth_n[mask] += valid_start

    depth_n *= 255
    depth_n = cv2.applyColorMap(depth_n[:, :, np.newaxis].astype(np.uint8), cv2.COLORMAP_PLASMA)

    return depth_n


def encode_rle(mask: list[list] | dict, height: int, width: int) -> dict:
    """Encode mask from polygons / uncompressed RLE / RLE to RLE.

    Args:
        mask: Mask as polygons / uncompressed RLE / RLE.
        height: Image height.
        width: Image width.

    Returns:
        Mask as RLE.
    """
    if isinstance(mask, list):
        return polygons_to_rle(mask, height, width)
    elif isinstance(mask, dict):
        if isinstance(mask["counts"], list):
            return urle_to_rle(mask)
        return mask
    raise ValueError("Mask must be a list of polygons or an uncompressed RLE")


def mask_to_rle(mask: Image.Image | np.ndarray) -> dict:
    """Encode mask from Pillow or NumPy array to RLE.

    Args:
        mask: Mask as Pillow or NumPy array.

    Returns:
        Mask as RLE.
    """
    mask_array = np.asfortranarray(mask)
    return mask_api.encode(mask_array)


def rle_to_mask(rle: dict[str, list[int] | bytes]) -> np.ndarray:
    """Decode mask from RLE to NumPy array.

    Args:
        rle: Mask as RLE.

    Returns:
        Mask as NumPy array.
    """
    return mask_api.decode(rle)


def polygons_to_rle(polygons: list[list], height: int, width: int) -> dict:
    """Encode mask from polygons to RLE.

    Args:
        polygons: Mask as polygons.
        height: Image height.
        width: Image width.

    Returns:
        Mask as RLE.
    """
    rles = mask_api.frPyObjects(polygons, height, width)
    return mask_api.merge(rles)


def rle_to_polygons(rle: dict[str, list[int] | bytes]) -> list[list]:
    """Encode mask from RLE to polygons.

    Args:
        rle: Mask as RLE.

    Returns:
        Mask as polygons.
    """
    if "size" not in rle:
        raise ValueError("RLE must have a size")
    h, w = rle["size"]
    polygons, _ = mask_to_polygons(rle_to_mask(rle))

    # Normalize point coordinates
    for p in polygons:
        p[::2] = [x / w for x in p[::2]]
        p[1::2] = [y / h for y in p[1::2]]

    return polygons


def mask_to_polygons(mask: np.ndarray) -> tuple[list[list], bool]:
    """Encode mask from NumPy array to polygons.

    Args:
        mask: Mask as NumPy array

    Returns:
        Tuple:
            - Mask as polygons
            - True if mask has holes
    """
    # Some versions of cv2 does not support incontiguous arr
    mask = np.ascontiguousarray(mask)

    # cv2.RETR_CCOMP flag retrieves all the contours and arranges them
    # to a 2-level hierarchy.
    # External contours (boundary) of the object are placed in hierarchy-1.
    # Internal contours (holes) are placed in hierarchy-2.
    # cv2.CHAIN_APPROX_NONE flag gets vertices of polygons from contours.
    res = cv2.findContours(mask.astype("uint8"), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    hierarchy = res[-1]

    # If mask is empty
    if hierarchy is None:
        return [], False

    # Check if mask has holes
    has_holes = (hierarchy.reshape(-1, 4)[:, 3] >= 0).sum() > 0

    res = res[-2]
    res = [x.flatten() for x in res]

    # The coordinates from OpenCV are integers in range [0, W-1 or H-1].
    # We add 0.5 to turn them into real-value coordinate space. A better solution
    # would be to first +0.5 and then dilate the returned polygon by 0.5.
    res = [x + 0.5 for x in res if len(x) >= 6]

    # Convert np.array to lists
    res = [x.tolist() for x in res]

    return res, has_holes


def urle_to_rle(urle: dict[str, list[int]]) -> dict[str, list[int] | bytes]:
    """Encode mask from uncompressed RLE to RLE.

    Args:
        urle: Mask as uncompressed RLE.

    Returns:
        Mask as RLE.
    """
    height, width = urle["size"]
    return mask_api.frPyObjects(urle, height, width)


def rle_to_urle(rle: dict[str, list[int] | bytes]) -> dict[str, list[int]]:
    """Encode mask from RLE to uncompressed RLE.

    Args:
        rle: Mask as RLE.

    Returns:
        Mask as uncompressed RLE.
    """
    if "counts" not in rle or rle["counts"] is None:
        raise ValueError("RLE must have counts")
    mask = rle_to_mask(rle)
    urle = {"counts": [], "size": list(mask.shape)}

    for i, (value, elements) in enumerate(groupby(mask.ravel(order="F"))):
        urle["counts"].append(0 if i == 0 and value == 1 else len(list(elements)))

    return urle


def mask_area(rle: dict[str, list[int] | bytes]) -> float:
    """Compute mask area.

    Args:
        rle: Mask as RLE

    Returns:
        Mask area
    """
    return float(mask_api.area(rle))


def image_to_base64(image: Image.Image, format: str | None = None) -> str:
    """Encode image from Pillow to base64.

    The image is returned as a base64 string formatted as
    "data:image/{image_format};base64,{base64}".

    Args:
        image: Pillow image.
        format: Image format.

    Returns:
        Image as base64.
    """
    if image.format is None and format is None:
        raise ValueError("Image format is not defined")

    buffered = io.BytesIO()
    out_format = format or image.format
    if out_format.upper() == "UNKNOWN":
        out_format = "JPEG"
    image.save(buffered, format=out_format)

    encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return f"data:image/{out_format.lower()};base64,{encoded}"


def base64_to_image(base64_image: str) -> Image.Image:
    """Decode image from base64 to Pillow.

    Expect the image to be formatted as "data:image/{image_format};base64,{base64}".

    Args:
        base64_image: Image as base64.

    Returns:
        Pillow image.
    """
    image_data = base64.b64decode(base64_image.split(",", maxsplit=1)[1].encode("utf-8"))
    return Image.open(io.BytesIO(image_data))


def get_image_thumbnail(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Get image thumbnail.

    Args:
        image: Pillow Image.
        size: Thumbnail size.

    Returns:
        Image thumbnail as Pillow.
    """
    if (
        not isinstance(size, tuple)
        or len(size) != 2
        or not isinstance(size[0], int)
        or not isinstance(size[1], int)
        or size[0] <= 0
        or size[1] <= 0
    ):
        raise ValueError(f"Invalid thumbnail size: {size}")
    thumbnail = image.copy()
    thumbnail.thumbnail(size)
    return thumbnail


def generate_text_image_base64(text: str, width: int = 128, height: int = 128, font_size: int = 16) -> str:
    """Generate a thumbnail displaying given text.

    Args:
        text: input text
        width: thumbnail width
        height: thumbnail height
        font_size: font size

    Returns:
        base64 image of given text.
    """
    image = Image.new("RGB", (width, height), "white")

    try:
        font = ImageFont.truetype("arial.ttf", size=font_size)
    except IOError:
        font = ImageFont.load_default(size=font_size)

    draw = ImageDraw.Draw(image)

    # Set text boundaries
    max_text_width = width - 10  # 5px margin on both sides
    x_start = 5  # Left margin
    y_start = 5  # Top margin
    line_height = font.size + 2  # Line spacing

    # Manually wrap text based on actual pixel width
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + " " + word if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_text_width:
            current_line = test_line  # Word fits, add it to the line
        else:
            lines.append(current_line)  # Save current line
            current_line = word  # Start new line with this word

    if current_line:
        lines.append(current_line)  # Add last line

    # Calculate vertical centering
    total_text_height = len(lines) * line_height
    y_position = y_start + (height - total_text_height) // 2

    # Draw text aligned to the left
    for line in lines:
        draw.text((x_start, y_position), line, fill="black", font=font)
        y_position += line_height

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")
