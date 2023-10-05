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

import numpy as np

from pixano.utils.image import rle_to_mask, urle_to_rle


def denormalize_coords(coord: list[float], height: int, width: int) -> list[float]:
    """Denormalize coordinates

    Args:
        coord (list[float]): Normalized coordinates
        height (int): Height
        width (int): Width

    Returns:
        list[float]: Unnormalized coordinates
    """

    denorm = []

    for i, c in enumerate(coord):
        if i % 2 == 0:
            denorm.append(c * width)
        else:
            denorm.append(c * height)

    return denorm


def normalize_coords(coord: list[float], height: int, width: int) -> list[float]:
    """Normalize coordinates

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
    """Return the smallest bounding box containing all the mask pixels

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
    """Return the smallest bounding box containing all the mask pixels

    Args:
        urle (dict): Mask as uncompressed RLE

    Returns:
        list[float]: Normalized xywh bounding box
    """

    return mask_to_bbox(rle_to_mask(urle_to_rle(urle)))


def format_bbox(bbox: list[float], confidence: float = 0.0) -> dict:
    """Convert bounding box to frontend format

    Args:
        bbox (list[float]): Bounding box
        confidence (float, optional): Bounding box confidence. Defaults to None.

    Returns:
        dict: Bounding box in frontend format
    """

    if bbox != [0.0, 0.0, 0.0, 0.0]:
        return {
            "x": float(bbox[0]),
            "y": float(bbox[1]),
            "width": float(bbox[2]),
            "height": float(bbox[3]),
            "predicted": confidence != 0.0,
            "confidence": confidence,
        }


def xywh_to_xyxy(xywh: list[float]) -> list[float]:
    """Convert bounding box coordinates from xywh (using top left point as reference) to xyxy

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
    """Convert bounding box coordinates from xyxy to xywh (using top left point as reference)

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
