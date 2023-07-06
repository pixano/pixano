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
from PIL import Image


def denormalize(coord: list[float], w: int, h: int) -> list[float]:
    """Denormalize coordinates

    Args:
        coord (list[float]): Normalized coordinates
        w (int): Width
        h (int): Height

    Returns:
        list[float]: Unnormalized coordinates
    """

    denorm = []

    for i, c in enumerate(coord):
        if i % 2 == 0:
            denorm.append(c * w)
        else:
            denorm.append(c * h)

    return denorm


def normalize(coord: list[float], w: int, h: int) -> list[float]:
    """Normalize coordinates

    Args:
        coord (list[float]): Unnormalized coordinates
        w (int): Width
        h (int): Height

    Returns:
        list[float]: Normalized coordinates
    """

    norm = []

    for i, c in enumerate(coord):
        if i % 2 == 0:
            norm.append(c / w)
        else:
            norm.append(c / h)

    return norm


def mask_to_bbox(mask: Image.Image) -> list[float]:
    """Returns the smallest bounding box containing all the mask pixels

    Args:
        mask (Image.Image): Mask as Pillow (or NumPy Array)

    Returns:
        list[float]: Normalized xywh bounding box
    """

    w_img, h_img = mask.size
    bool_mask = np.array(mask).astype(bool)

    # Find all columns and rows that contain ones
    rows = np.any(bool_mask, axis=1)
    cols = np.any(bool_mask, axis=0)

    # Find the min and max col/row index that contain ones
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    # Calculate height and width
    h = (rmax - rmin + 1) / h_img
    w = (cmax - cmin + 1) / w_img

    return [cmin / w_img, rmin / h_img, w, h]


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
