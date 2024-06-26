# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import unittest

import numpy as np

from pixano.utils.boxes import (
    denormalize_coords,
    mask_to_bbox,
    normalize_coords,
    urle_to_bbox,
    xywh_to_xyxy,
    xyxy_to_xywh,
)
from pixano.utils.image import mask_to_rle, rle_to_urle


class BoxesTestCase(unittest.TestCase):
    """Bounding boxes utils test case"""

    def test_denormalize_coords(self):
        """Test denormalize_coords function"""

        denormalized_coords = [40, 50, 10, 10]
        width = 100
        height = 100
        normalized_coords = [0.4, 0.5, 0.1, 0.1]

        self.assertEqual(
            denormalize_coords(normalized_coords, height, width),
            denormalized_coords,
        )

    def test_normalize_coords(self):
        """Test normalize_coords function"""

        denormalized_coords = [40, 50, 10, 10]
        width = 100
        height = 100
        normalized_coords = [0.4, 0.5, 0.1, 0.1]

        self.assertEqual(
            normalize_coords(denormalized_coords, height, width),
            normalized_coords,
        )

    def test_mask_to_bbox(self):
        """Test mask_to_bbox function"""

        mask = np.array(
            [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            dtype="uint8",
        )
        bbox = [0.4, 0.5, 0.1, 0.1]

        self.assertEqual(mask_to_bbox(mask), bbox)

    def test_urle_to_bbox(self):
        """Test urle_to_bbox function"""

        mask = np.array(
            [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            dtype="uint8",
        )
        urle = rle_to_urle(mask_to_rle(mask))
        bbox = [0.4, 0.5, 0.1, 0.1]

        self.assertEqual(urle_to_bbox(urle), bbox)

    def test_xywh_to_xyxy(self):
        """Test xywh_to_xyxy function"""

        xywh_coords = [40, 50, 10, 10]
        xyxy_coords = [40, 50, 50, 60]

        self.assertEqual(xywh_to_xyxy(xywh_coords), xyxy_coords)

    def test_xyxy_to_xywh(self):
        """Test xyxy_to_xywh function"""

        xywh_coords = [40, 50, 10, 10]
        xyxy_coords = [40, 50, 50, 60]

        self.assertEqual(xyxy_to_xywh(xyxy_coords), xywh_coords)
