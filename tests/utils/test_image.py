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

import unittest

import numpy as np
from PIL import Image

from pixano.utils.image import (
    binary_to_url,
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


class ImageUtilsTestCase(unittest.TestCase):
    """Image utils test case"""

    def setUp(self):
        self.im = Image.new("RGB", (100, 100))

    def test_image_to_binary(self):
        """Test image_to_binary function"""

        im_bytes = image_to_binary(self.im)

        self.assertIsInstance(im_bytes, bytes)

    def test_image_to_thumbnail(self):
        """Test image_to_thumbnail function"""

        im_thumbnail = image_to_thumbnail(self.im)

        self.assertIsInstance(im_thumbnail, bytes)

    def test_binary_to_url(self):
        """Test binary_to_url function"""

        im_bytes = image_to_binary(self.im)
        im_url = binary_to_url(im_bytes)

        self.assertIsInstance(im_url, str)

    def test_depth_file_to_binary(self):
        """Test depth_file_to_binary function"""

        path = "tests/assets/depth_images/000067.png"
        file_bytes = depth_file_to_binary(path)

        self.assertIsInstance(file_bytes, bytes)

    def test_encode_rle(self):
        """Test encode_rle function"""

        rle = {"size": [10, 10], "counts": b"]12810Oh0"}
        urle = {"counts": [45, 2, 8, 3, 8, 2, 32], "size": [10, 10]}
        # Polygons to RLE using pycocotools reduces the mask size
        polygons = [
            [
                3.5,
                4.5,
                3.5,
                5.5,
                3.5,
                6.5,
                4.5,
                7.5,
                5.5,
                7.5,
                6.5,
                7.5,
                6.5,
                6.5,
                5.5,
                5.5,
                4.5,
                4.5,
            ]
        ]

        self.assertEqual(encode_rle(rle, height=10, width=10), rle)
        self.assertEqual(encode_rle(urle, height=10, width=10), rle)
        self.assertEqual(encode_rle(polygons, height=10, width=10), rle)

    def test_mask_to_polygons(self):
        """Test mask_to_polygons function"""

        mask = np.array(
            [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            dtype="uint8",
        )
        polygons = [[4.5, 5.5, 4.5, 6.5, 5.5, 7.5, 6.5, 7.5, 6.5, 6.5, 5.5, 5.5]]
        has_holes = False

        self.assertEqual(mask_to_polygons(mask), (polygons, has_holes))

    def test_mask_to_rle(self):
        """Test mask_to_rle function"""

        mask = np.array(
            [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            dtype="uint8",
        )
        rle = {"size": [10, 10], "counts": b"]12810Oh0"}

        self.assertEqual(mask_to_rle(mask), rle)

    def test_polygons_to_rle(self):
        """Test polygons_to_rle function"""

        actual_mask = np.array(
            [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            dtype="uint8",
        )
        # Polygons to RLE using pycocotools reduces the mask size
        polygon_mask = np.array(
            [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 1, 1, 0, 0, 0, 0, 0],
                [0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
                [0, 0, 0, 1, 1, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            dtype="uint8",
        )
        polygons = mask_to_polygons(polygon_mask)[0]
        print(polygons)
        rle_from_polygons = polygons_to_rle(polygons, height=10, width=10)

        np.testing.assert_array_equal(rle_to_mask(rle_from_polygons), actual_mask)

    def test_rle_to_mask(self):
        """Test rle_to_mask function"""

        rle = {"size": [10, 10], "counts": b"]12810Oh0"}
        mask = np.array(
            [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ],
            dtype="uint8",
        )

        np.testing.assert_array_equal(rle_to_mask(rle), mask)

    def test_rle_to_polygons(self):
        """Test rle_to_polygons function"""

        rle = {"size": [10, 10], "counts": b"]12810Oh0"}
        normalized_polygons = [
            [
                0.45,
                0.55,
                0.45,
                0.65,
                0.55,
                0.75,
                0.65,
                0.75,
                0.65,
                0.65,
                0.55,
                0.55,
            ]
        ]

        self.assertEqual(rle_to_polygons(rle), normalized_polygons)

    def test_rle_to_urle(self):
        """Test rle_to_urle function"""

        rle = {"size": [10, 10], "counts": b"]12810Oh0"}
        urle = {"counts": [45, 2, 8, 3, 8, 2, 32], "size": [10, 10]}

        self.assertEqual(rle_to_urle(rle), urle)

    def test_urle_to_rle(self):
        """Test urle_to_rle function"""

        rle = {"size": [10, 10], "counts": b"]12810Oh0"}
        urle = {"counts": [45, 2, 8, 3, 8, 2, 32], "size": [10, 10]}

        self.assertEqual(urle_to_rle(urle), rle)
