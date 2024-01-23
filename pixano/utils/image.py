# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import base64
from io import BytesIO
from itertools import groupby

import cv2
import numpy as np
from PIL import Image
from pycocotools import mask as mask_api


def image_to_binary(image: Image.Image, im_format: str = "PNG") -> bytes:
    """Encode image from Pillow to binary

    Args:
        image (Image.Image): Image as Pillow
        im_format (str, optional): Image file extension. Defaults to "PNG".

    Returns:
        bytes: Image as binary
    """

    if image is None:
        return None

    with BytesIO() as output_bytes:
        image.save(output_bytes, im_format)
        im_bytes = output_bytes.getvalue()

    return im_bytes


def image_to_thumbnail(image: bytes | Image.Image) -> bytes:
    """Generate image thumbnail

    Args:
        image (bytes | Image.Image): Image as binary or as Pillow

    Returns:
        bytes: Image thumbnail as binary
    """

    if isinstance(image, bytes):
        image = Image.open(BytesIO(image))

    image.thumbnail((128, 128))
    return image_to_binary(image)


def binary_to_url(im_bytes: bytes) -> str:
    """Encode image from binary to base 64 URL

    Args:
        im_bytes (bytes): Image as binary

    Returns:
        str: Image base 64 URL
    """

    if im_bytes is not None:
        encoded = base64.b64encode(im_bytes).decode("utf-8")
        return f"data:image;base64,{encoded}"
    return ""


def depth_file_to_binary(depth_path: str) -> bytes:
    """Encode depth file to RGB image in binary

    Args:
        depth_path (str): Depth file path

    Returns:
        bytes: Depth file as RGB image in binary
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
    """Encode depth array to gray levels

    Args:
        depth (np.ndarray): Depth array
        valid_start (float, optional): Valid start. Defaults to 0.2.
        valid_end (float, optional): Valid end. Defaults to 1.
        scale (float, optional): Scale. Defaults to 1.0.

    Returns:
        np.ndarray: Depth array in gray levels
    """

    mask = depth > 1

    # Scale gives depth in mm
    depth_n = depth * scale * 0.001

    if mask.sum() > 0:
        depth_n[mask] -= depth_n[mask].min()
        depth_n[mask] /= depth_n[mask].max() / (valid_end - valid_start)
        depth_n[mask] += valid_start

    depth_n *= 255
    depth_n = cv2.applyColorMap(
        depth_n[:, :, np.newaxis].astype(np.uint8), cv2.COLORMAP_PLASMA
    )

    return depth_n


def encode_rle(mask: list[list] | dict, height: int, width: int) -> dict:
    """Encode mask from polygons / uncompressed RLE / RLE to RLE

    Args:
        mask (list[list] | dict): Mask as polygons / uncompressed RLE / RLE
        height (int): Image height
        width (int): Image width

    Returns:
        dict: Mask as RLE
    """

    if isinstance(mask, list):
        return polygons_to_rle(mask, height, width)
    if isinstance(mask, dict):
        if isinstance(mask["counts"], list):
            return urle_to_rle(mask)
        return mask
    return None


def mask_to_rle(mask: Image.Image) -> dict:
    """Encode mask from Pillow or NumPy array to RLE

    Args:
        mask (Image.Image): Mask as Pillow or NumPy array

    Returns:
        dict: Mask as RLE
    """

    if mask is not None:
        mask_array = np.asfortranarray(mask)
        return mask_api.encode(mask_array)
    return None


def rle_to_mask(rle: dict[str, list[int] | bytes]) -> np.ndarray:
    """Decode mask from RLE to NumPy array

    Args:
        rle (dict[str, list[int] | bytes]): Mask as RLE

    Returns:
        np.ndarray: Mask as NumPy array
    """

    if rle is not None:
        return mask_api.decode(rle)
    return None


def polygons_to_rle(polygons: list[list], height: int, width: int) -> dict:
    """Encode mask from polygons to RLE

    Args:
        polygons (list[list]): Mask as polygons
        height (int): Image height
        width (int): Image width

    Returns:
        dict: Mask as RLE
    """

    if polygons is not None:
        rles = mask_api.frPyObjects(polygons, height, width)
        return mask_api.merge(rles)
    return None


def rle_to_polygons(rle: dict[str, list[int] | bytes]) -> list[list]:
    """Encode mask from RLE to polygons

    Args:
        rle (dict[str, list[int] | bytes]): Mask as RLE

    Returns:
        list[list]: Mask as polygons
    """

    if rle is not None and "size" in rle:
        h, w = rle["size"]
        polygons, _ = mask_to_polygons(rle_to_mask(rle))

        # Normalize point coordinates
        for p in polygons:
            p[::2] = [x / w for x in p[::2]]
            p[1::2] = [y / h for y in p[1::2]]

        return polygons
    return None


def mask_to_polygons(mask: np.ndarray) -> tuple[list[list], bool]:
    """Encode mask from NumPy array to polygons

    Args:
        mask (np.ndarray): Mask as NumPy array

    Returns:
        list[list]: Mask as polygons
        bool: True if mask has holes
    """

    if mask is not None:
        # Some versions of cv2 does not support incontiguous arr
        mask = np.ascontiguousarray(mask)

        # cv2.RETR_CCOMP flag retrieves all the contours and arranges them to a 2-level hierarchy.
        # External contours (boundary) of the object are placed in hierarchy-1.
        # Internal contours (holes) are placed in hierarchy-2.
        # cv2.CHAIN_APPROX_NONE flag gets vertices of polygons from contours.
        res = cv2.findContours(
            mask.astype("uint8"), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE
        )
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

    return [], False


def urle_to_rle(urle: dict[str, list[int]]) -> dict[str, list[int] | bytes]:
    """Encode mask from uncompressed RLE to RLE

    Args:
        urle (dict[str, list[int]]): Mask as uncompressed RLE

    Returns:
        dict[str, list[int] | bytes]: Mask as RLE
    """

    if urle is not None:
        height, width = urle["size"]
        return mask_api.frPyObjects(urle, height, width)
    return None


def rle_to_urle(rle: dict[str, list[int] | bytes]) -> dict[str, list[int]]:
    """Encode mask from RLE to uncompressed RLE

    Args:
        rle (dict[str, list[int] | bytes]): Mask as RLE

    Returns:
        dict[str, list[int]]: Mask as uncompressed RLE
    """

    if rle is not None and rle["counts"] is not None:
        mask = rle_to_mask(rle)
        urle = {"counts": [], "size": list(mask.shape)}

        for i, (value, elements) in enumerate(groupby(mask.ravel(order="F"))):
            urle["counts"].append(0 if i == 0 and value == 1 else len(list(elements)))

        return urle
    return None
