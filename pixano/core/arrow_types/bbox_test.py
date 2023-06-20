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

import subprocess
import unittest

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .bbox import BBox, BBoxArray


class BBoxTestCase(unittest.TestCase):
    def setUp(self):
        self.xyxy_coords = [0.1, 0.2, 0.3, 0.4]
        self.xywh_coords = [0.1, 0.2, 0.3, 0.4]
        self.bbox_xyxy = BBox.from_xyxy(self.xyxy_coords)
        self.bbox_xywh = BBox.from_xywh(self.xywh_coords)

    def test_format_property(self):
        self.assertEqual(self.bbox_xyxy.format, "xyxy")
        self.assertEqual(self.bbox_xywh.format, "xywh")

    def test_is_normalized_property(self):
        self.assertTrue(self.bbox_xyxy.is_normalized)
        self.assertTrue(self.bbox_xywh.is_normalized)

    def test_to_xyxy(self):
        converted_coords = self.bbox_xyxy.to_xyxy()
        self.assertTrue(np.allclose(converted_coords, self.xyxy_coords))

    def test_to_xywh(self):
        converted_coords = self.bbox_xywh.to_xywh()
        self.assertTrue(np.allclose(converted_coords, self.xywh_coords))

    def test_format_conversion(self):
        self.bbox_xyxy.format_xywh()
        self.assertEqual(self.bbox_xyxy.format, "xywh")
        self.assertTrue(np.allclose(self.bbox_xyxy.to_xywh(), [0.1, 0.2, 0.2, 0.2]))

        self.bbox_xywh.format_xyxy()
        self.assertEqual(self.bbox_xywh.format, "xyxy")
        self.assertTrue(np.allclose(self.bbox_xywh.to_xyxy(), [0.1, 0.2, 0.4, 0.6]))

    def test_normalize(self):
        self.bbox_to_normalize = BBox.from_xyxy([10, 10, 20, 20])
        height = 100
        width = 200
        self.bbox_to_normalize.normalize(height, width)
        self.assertTrue(
            np.allclose(self.bbox_to_normalize.to_xyxy(), [0.05, 0.1, 0.1, 0.2])
        )

class BBoxTableTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.bbox_list = [
            BBox([0.1, 0.2, 0.3, 0.4], "xyxy", True),
            BBox([0.1, 0.2, 0.2, 0.2], "xywh", True),
            BBox([12, 2.9, 3.3, 7], "xyxy", False),
        ]

    def test_bbox_table(self):
        bbox_arr = BBoxArray.from_BBox_list(self.bbox_list)

        table = pa.Table.from_arrays([bbox_arr], names=["bbox"])
        pq.write_table(table, "test_bbox.parquet", store_schema=True)

        re_table = pq.read_table("test_bbox.parquet")
        self.assertEqual(re_table.column_names, ["bbox"])
        Bbox0 = re_table.take([0])["bbox"][0].as_py()
        self.assertTrue(isinstance(Bbox0, BBox))

    def test_bbox_table_with_panda(self):
        bbox_arr = BBoxArray.from_BBox_list(self.bbox_list)

        pd_bbox = bbox_arr.to_pandas()

        df = pd.DataFrame(pd_bbox, columns=["bbox"])
        pd_table = pa.Table.from_pandas(df)

        pq.write_table(pd_table, "test_bbox.parquet")

        reload_pd_table = pq.read_pandas("test_bbox.parquet")
        BBox1 = reload_pd_table.take([0])["bbox"][0].as_py()

        self.assertEqual(reload_pd_table.column_names, ["bbox"])
        # panda give dict
        self.assertTrue(isinstance(BBox1, dict))
    
    @classmethod
    def tearDownClass(cls):
        subprocess.run(["make", "clean"])
        None
