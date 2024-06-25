# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from pixano.features import Pose, PoseType


class PoseTestCase(unittest.TestCase):
    """Pose test case"""


class TestParquetPose(unittest.TestCase):
    """Pose test case for Parquet storage"""

    def setUp(self):
        """Tests setup"""

        cam_r_m2c0, cam_t_m2c0 = [1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 1, 1]
        cam_r_m2c1, cam_t_m2c1 = [2, 4, 6, 8, 1, 3, 5, 7, 9], [2, 2, 2]

        self.pose_list = [Pose(cam_r_m2c0, cam_t_m2c0), Pose(cam_r_m2c1, cam_t_m2c1)]

    def test_pose_table(self):
        """Test Pose Parquet storage"""

        pose_arr = PoseType.Array.from_pylist(self.pose_list)
        table = pa.Table.from_arrays(
            [pose_arr], schema=pa.schema([pa.field("pose", PoseType)])
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["pose"])

        pose1 = re_table.take([1])["pose"][0].as_py()

        self.assertIsInstance(pose1, Pose)
