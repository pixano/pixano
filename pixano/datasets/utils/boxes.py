# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np

from .image import rle_to_mask, urle_to_rle


def denormalize_coords(coord: list[float], height: int, width: int, rounded_int=True) -> list[float]:
    """Denormalize coordinates.

    Args:
        coord (list[float]): Normalized coordinates
        height (int): Height
        width (int): Width
        rounded_int (bool): True to round denormalized float to nearest integer.
            Default to True

    Returns:
        list[float]: Unnormalized coordinates,
    """
    denorm = []

    for i, c in enumerate(coord):
        if i % 2 == 0:
            denorm.append(round(c * width) if rounded_int else c * width)
        else:
            denorm.append(round(c * height) if rounded_int else c * height)

    return denorm


def normalize_coords(coord: list[float], height: int, width: int) -> list[float]:
    """Normalize coordinates.

    Args:
        coord (list[float]): Unnormalized coordinates
        height (int): Height
        width (int): Width

    Returns:
        list[float]: Normalized coordinates
    """
    norm = []

    for i, c in enumerate(coord):
        if i % 2 == 0:
            norm.append(c / width)
        else:
            norm.append(c / height)

    return norm


def mask_to_bbox(mask: np.ndarray) -> list[float]:
    """Return the smallest bounding box containing all the mask pixels.

    Args:
        mask (np.ndarray): Mask as NumPy Array

    Returns:
        list[float]: Normalized xywh bounding box
    """
    height, width = mask.shape
    bool_mask = np.array(mask).astype(bool)

    # Find all columns and rows that contain ones
    rows = np.any(bool_mask, axis=1)
    cols = np.any(bool_mask, axis=0)

    # Find the min and max col/row index that contain ones
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    # Calculate bbox height and width
    w = (cmax - cmin + 1) / width
    h = (rmax - rmin + 1) / height

    return [cmin / width, rmin / height, w, h]


def urle_to_bbox(urle: dict) -> list[float]:
    """Return the smallest bounding box containing all the mask pixels.

    Args:
        urle (dict): Mask as uncompressed RLE

    Returns:
        list[float]: Normalized xywh bounding box
    """
    return mask_to_bbox(rle_to_mask(urle_to_rle(urle)))


def xywh_to_xyxy(xywh: list[float]) -> list[float]:
    """Convert bounding box coordinates from xywh
    (using top left point as reference) to xyxy.

    Args:
        xywh (list[float]): xywh coordinates

    Returns:
        list[float]: xyxy coordinates
    """
    return [
        float(xywh[0]),
        float(xywh[1]),
        float(xywh[0] + xywh[2]),
        float(xywh[1] + xywh[3]),
    ]


def xyxy_to_xywh(xyxy: list[float]) -> list[float]:
    """Convert bounding box coordinates from xyxy to xywh
    (using top left point as reference).

    Args:
        xyxy (list[float]): xyxy coordinates

    Returns:
        list[float]: xywh coordinates
    """
    return [
        float(xyxy[0]),
        float(xyxy[1]),
        float(xyxy[2] - xyxy[0]),
        float(xyxy[3] - xyxy[1]),
    ]
