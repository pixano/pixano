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

import pyarrow as pa
import pyarrow.parquet as pq

from pixano.core import Camera, CameraType


class CameraTestCase(unittest.TestCase):
    """Camera test case"""

    def setUp(self):
        """Tests setup"""

        self.depth_scale = 0.5
        self.cam_k = [0.2, 0.6, 0.3]
        self.cam_r_w2c = [0.2, 0.6, 0.3, 0.2, 0.6, 0.3, 0.2, 0.6, 0.3]
        self.cam_t_w2c = [0.2, 0.6, 0.3]

    def test_init(self):
        """Test Camera init method"""

        partial_camera = Camera(
            depth_scale=self.depth_scale,
            cam_k=self.cam_k,
        )
        full_camera = Camera(
            depth_scale=self.depth_scale,
            cam_k=self.cam_k,
            cam_r_w2c=self.cam_r_w2c,
            cam_t_w2c=self.cam_t_w2c,
        )

        self.assertEqual(partial_camera.depth_scale, self.depth_scale)
        self.assertEqual(partial_camera.cam_k, self.cam_k)
        self.assertEqual(partial_camera.cam_r_w2c, [0.0] * 9)
        self.assertEqual(partial_camera.cam_t_w2c, [0.0] * 3)

        self.assertEqual(full_camera.depth_scale, self.depth_scale)
        self.assertEqual(full_camera.cam_k, self.cam_k)
        self.assertEqual(full_camera.cam_r_w2c, self.cam_r_w2c)
        self.assertEqual(full_camera.cam_t_w2c, self.cam_t_w2c)


class TestParquetCamera(unittest.TestCase):
    """Camera test case for Parquet storage"""

    def setUp(self):
        """Tests setup"""

        self.depth_scale = 0.5
        self.cam_k = [0.2, 0.6, 0.3]
        self.cam_r_w2c = [0.2, 0.6, 0.3, 0.2, 0.6, 0.3, 0.2, 0.6, 0.3]
        self.cam_t_w2c = [0.2, 0.6, 0.3]

        self.camera_list = [
            Camera(
                depth_scale=self.depth_scale,
                cam_k=self.cam_k,
            ),
            Camera(
                depth_scale=self.depth_scale,
                cam_k=self.cam_k,
                cam_r_w2c=self.cam_r_w2c,
                cam_t_w2c=self.cam_t_w2c,
            ),
        ]

    def test_camera_table(self):
        """Test Camera Parquet storage"""

        cam_arr = CameraType.Array.from_pylist(self.camera_list)
        table = pa.Table.from_arrays(
            [cam_arr],
            schema=pa.schema([pa.field("camera", CameraType)]),
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["camera"])

        cam_1 = re_table.take([0])["camera"][0].as_py()

        self.assertIsInstance(cam_1, Camera)
