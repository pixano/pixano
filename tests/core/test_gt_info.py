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

from pixano.core import BBox, GtInfo, GtInfoType


class GtInfoTestCase(unittest.TestCase):
    """GtInfo test case"""

    def setUp(self):
        """Tests setup"""

        self.bbox_obj = BBox([0.1, 0.1, 0.1, 0.1], "xywh")
        self.bbox_visib = BBox([0.2, 0.2, 0.1, 0.1], "xywh")
        self.px_count_all = 10
        self.px_count_valid = 5
        self.px_count_visib = 5
        self.visib_fract = 0.5

    def test_init(self):
        """Test GtInfo init method"""

        gtinfo = GtInfo(
            bbox_obj=self.bbox_obj,
            bbox_visib=self.bbox_visib,
            px_count_all=self.px_count_all,
            px_count_valid=self.px_count_valid,
            px_count_visib=self.px_count_visib,
            visib_fract=self.visib_fract,
        )

        self.assertEqual(gtinfo.bbox_obj, self.bbox_obj)
        self.assertEqual(gtinfo.bbox_visib, self.bbox_visib)
        self.assertEqual(gtinfo.px_count_all, self.px_count_all)
        self.assertEqual(gtinfo.px_count_valid, self.px_count_valid)
        self.assertEqual(gtinfo.px_count_visib, self.px_count_visib)
        self.assertEqual(gtinfo.visib_fract, self.visib_fract)


class TestParquetGtInfo(unittest.TestCase):
    """GtInfo test case for Parquet storage"""

    def setUp(self):
        """Tests setup"""

        self.bbox_obj = BBox([0.1, 0.1, 0.1, 0.1], "xywh")
        self.bbox_visib = BBox([0.2, 0.2, 0.1, 0.1], "xywh")
        self.px_count_all = 10
        self.px_count_valid = 5
        self.px_count_visib = 5
        self.visib_fract = 0.5

        self.gtinfo_list = [
            GtInfo(
                bbox_obj=self.bbox_obj,
                bbox_visib=self.bbox_visib,
                px_count_all=self.px_count_all,
                px_count_valid=self.px_count_valid,
                px_count_visib=self.px_count_visib,
                visib_fract=self.visib_fract,
            )
        ]

    def test_gt_info_table(self):
        """Test GtInfo Parquet storage"""

        gt_arr = GtInfoType.Array.from_pylist(self.gtinfo_list)
        table = pa.Table.from_arrays(
            [gt_arr],
            schema=pa.schema([pa.field("gtinfo", GtInfoType)]),
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["gtinfo"])

        gt_1 = re_table.take([0])["gtinfo"][0].as_py()

        self.assertIsInstance(gt_1, GtInfo)
