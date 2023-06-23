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
import pyarrow as pa
import pyarrow.parquet as pq
from pose import Pose, PoseArray, PoseType


class PoseTestCase(unittest.TestCase):
    pass


class TestParquetPose(unittest.TestCase):
    def setUp(self) -> None:
        cam_R_m2c0, cam_R_m2c1 = [i % 2.4 for i in range(9)], [
            i % 1.7 for i in range(9)
        ]
        cam_t_m2c0, cam_t_m2c1 = [i for i in range(3)], [3 * i for i in range(3)]

        self.pose_list = [Pose(cam_R_m2c0, cam_t_m2c0), Pose(cam_R_m2c1, cam_t_m2c1)]

    def test_pose_table(self):
        pose_array = PoseArray.from_Pose_list(self.pose_list)

        schema = pa.schema(
            [
                pa.field("pose", PoseType()),
            ]
        )
        table = pa.Table.from_arrays([pose_array], schema=schema)
        pq.write_table(table, "test_pose.parquet", store_schema=True)
        re_table = pq.read_table("test_pose.parquet")

        self.assertEqual(re_table.column_names, ["pose"])
        pose1 = re_table.take([1])["pose"][0].as_py()
        self.assertTrue(isinstance(pose1, Pose))
