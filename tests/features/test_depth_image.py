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

import tempfile
import unittest

import imageio
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pixano.features import DepthImage, DepthImageType


class DepthImageTestCase(unittest.TestCase):
    """DepthImage test case"""

    def setUp(self):
        """Tests setup"""

        self.depth_map = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
        self.shape = self.depth_map.shape
        self.bytes = self.depth_map.tobytes()
        self.depth_image = DepthImage(
            depth_map=self.depth_map,
            shape=self.shape,
            bytes=self.bytes,
        )

    def test_bytes(self):
        """Test DepthImage bytes property"""

        depth_image_bytes = self.depth_image.bytes

        self.assertEqual(depth_image_bytes, self.bytes)

    def test_depth_map(self):
        """Test DepthImage depth_map property"""

        image_without_depth_map = DepthImage(shape=self.shape, bytes=self.bytes)
        depth_map_from_bytes = image_without_depth_map.depth_map

        self.assertIsInstance(self.depth_image.depth_map, np.ndarray)
        self.assertIsInstance(depth_map_from_bytes, np.ndarray)
        self.assertEqual(self.depth_image.depth_map.tolist(), self.depth_map.tolist())
        self.assertEqual(depth_map_from_bytes.tolist(), self.depth_map.tolist())

    def test_load_npy(self):
        """Test DepthImage load_npy method"""

        with tempfile.NamedTemporaryFile(suffix=".npy") as tmp_file:
            np.save(tmp_file.name, self.depth_map)
            depth_image = DepthImage.load_npy(tmp_file.name)

            self.assertIsInstance(depth_image, DepthImage)
            self.assertEqual(depth_image.depth_map.tolist(), self.depth_map.tolist())

    def test_load(self):
        """Test DepthImage load method"""

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            imageio.v3.imwrite(tmp_file.name, self.depth_map.astype(np.uint16))
            depth_image = DepthImage.load(tmp_file.name)

            self.assertIsInstance(depth_image, DepthImage)
            self.assertEqual(depth_image.depth_map.tolist(), self.depth_map.tolist())

    def test_save(self):
        """Test DepthImage save method"""

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            self.depth_image.save(tmp_file.name)
            loaded_image = imageio.v3.imread(tmp_file.name)

            self.assertIsInstance(loaded_image, np.ndarray)
            self.assertEqual(loaded_image.tolist(), self.depth_map.tolist())

    def test_open(self):
        """Test DepthImage open method"""

        io_obj = self.depth_image.open()
        self.assertIsNotNone(io_obj)

        loaded_bytes = io_obj.read()
        self.assertEqual(loaded_bytes, self.bytes)

    def test_display(self):
        """Test DepthImage display method"""

        self.depth_image.display()

    def test_to_grayscale(self):
        """Test DepthImage to_grayscale method"""

        gray_image = self.depth_image.to_grayscale()

        self.assertIsInstance(gray_image, DepthImage)
        self.assertEqual(gray_image.depth_map.dtype, np.uint8)
        self.assertEqual(gray_image.depth_map.tolist(), [[0, 51, 102], [153, 204, 255]])


class TestParquetDepthImage(unittest.TestCase):
    """DepthImage test case for Parquet storage"""

    def setUp(self) -> None:
        """Tests setup"""

        uri1 = "tests/assets/depth_images/000067.png"
        uri2 = "tests/assets/depth_images/000934.png"

        self.depth_image1 = DepthImage.load(uri1)
        self.depth_image2 = DepthImage.load(uri2)

        self.depth_image_list = [
            self.depth_image1,
            self.depth_image2,
        ]

    def test_depth_image_table(self):
        """Test DepthImage Parquet storage"""

        depth_image_arr = DepthImageType.Array.from_pylist(self.depth_image_list)
        table = pa.Table.from_arrays(
            [depth_image_arr],
            schema=pa.schema([pa.field("DepthImage", DepthImageType)]),
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["DepthImage"])

        depth_image0 = re_table.take([0])["DepthImage"][0].as_py()

        self.assertIsInstance(depth_image0, DepthImage)
