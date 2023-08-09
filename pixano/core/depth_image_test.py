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
from pathlib import Path


import imageio
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pixano.core.depth_image import DepthImage, DepthImageType


class DepthImageTestCase(unittest.TestCase):
    def setUp(self):
        # Création d'une image de profondeur fictive
        self.depth_map = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint16)
        self.shape = self.depth_map.shape
        self.bytes = self.depth_map.tobytes()
        self.depth_image = DepthImage(
            depth_map=self.depth_map, shape=self.shape, bytes=self.bytes
        )

    def test_bytes_property(self):
        bytes = self.depth_image.bytes
        self.assertEqual(bytes, self.bytes)

    def test_depth_map_property(self):
        depth_map = self.depth_image.depth_map
        self.assertIsInstance(depth_map, np.ndarray)
        self.assertEqual(depth_map.tolist(), self.depth_map.tolist())

    def test_load_npy(self):
        with tempfile.NamedTemporaryFile(suffix=".npy") as tmp_file:
            np.save(tmp_file.name, self.depth_map)
            depth_image = DepthImage.load_npy(tmp_file.name)
            self.assertIsInstance(depth_image, DepthImage)
            self.assertEqual(depth_image.depth_map.tolist(), self.depth_map.tolist())

    def test_load(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            imageio.v3.imwrite(tmp_file.name, self.depth_map.astype(np.uint16))
            depth_image = DepthImage.load(tmp_file.name)
            self.assertIsInstance(depth_image, DepthImage)
            self.assertEqual(depth_image.depth_map.tolist(), self.depth_map.tolist())

    def test_save(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            self.depth_image.save(tmp_file.name)
            loaded_image = imageio.v3.imread(tmp_file.name)
            self.assertIsInstance(loaded_image, np.ndarray)
            self.assertEqual(loaded_image.tolist(), self.depth_map.tolist())

    def test_open(self):
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_path = Path(tmp_file.name)
            io_obj = self.depth_image.open()
            self.assertIsNotNone(io_obj)
            # Vérification que les données ouvertes correspondent aux données initiales
            loaded_bytes = io_obj.read()
            self.assertEqual(loaded_bytes, self.bytes)

    def test_to_grayscale(self):
        gray_image = self.depth_image.to_grayscale()
        self.assertIsInstance(gray_image, DepthImage)
        self.assertEqual(gray_image.depth_map.dtype, np.uint8)
        self.assertEqual(gray_image.depth_map.tolist(), [[0, 51, 102], [153, 204, 255]])


class TestParquetDepthImage(unittest.TestCase):
    def setUp(self) -> None:
        uri1 = "unit_testing/assets/depth_images/000067.png"
        uri2 = "unit_testing/assets/depth_images/000934.png"
        uri3 = "unit_testing/assets/depth_images/20170320_144339_cam_0_00011901.npy"

        self.depth_image1 = DepthImage.load(uri1)
        self.depth_image2 = DepthImage.load(uri2)
        self.depth_image3 = DepthImage.load_npy(uri3)

        self.depth_image_list = [
            self.depth_image1,
            self.depth_image2,
            self.depth_image3,
        ]

    def test_depth_image_table(self):
        depth_image_array = DepthImageType.Array.from_pylist(self.depth_image_list)

        schema = pa.schema(
            [
                pa.field("DepthImage", DepthImageType),
            ]
        )
        table = pa.Table.from_arrays([depth_image_array], schema=schema)

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["DepthImage"])
        depth_image0 = re_table.take([0])["DepthImage"][0].as_py()
        self.assertTrue(isinstance(depth_image0, DepthImage))
