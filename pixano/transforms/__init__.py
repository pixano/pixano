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

import re

from .boxes import (
    denormalize,
    format_bbox,
    mask_to_bbox,
    normalize,
    urle_to_bbox,
    xywh_to_xyxy,
    xyxy_to_xywh,
)
from .image import (
    binary_to_url,
    depth_array_to_gray,
    depth_file_to_binary,
    encode_rle,
    image_to_binary,
    image_to_thumbnail,
    mask_to_polygons,
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)
from .labels import coco_ids_80to91, coco_names_80, coco_names_91, dota_ids, voc_names

__all__ = [
    "normalize",
    "denormalize",
    "mask_to_bbox",
    "urle_to_bbox",
    "format_bbox",
    "xywh_to_xyxy",
    "xyxy_to_xywh",
    "image_to_binary",
    "image_to_thumbnail",
    "binary_to_url",
    "depth_file_to_binary",
    "depth_array_to_gray",
    "encode_rle",
    "mask_to_rle",
    "rle_to_mask",
    "polygons_to_rle",
    "rle_to_polygons",
    "mask_to_polygons",
    "urle_to_rle",
    "rle_to_urle",
    "coco_ids_80to91",
    "coco_names_80",
    "coco_names_91",
    "dota_ids",
    "voc_names",
    "natural_key",
]


def natural_key(string: str) -> list:
    """Return key for string natural sort

    Args:
        string (str): Input string

    Returns:
        list: Sort key
    """
    return [int(s) if s.isdecimal() else s for s in re.split(r"(\d+)", string)]
