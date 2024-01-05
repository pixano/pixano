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

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pixano.core import BBox, BBoxType


class BBoxTestCase(unittest.TestCase):
    """BBox test case"""

    def setUp(self):
        """Tests setup"""

        self.height = 4
        self.width = 6
        self.coords = {
            "xyxy": [1, 1, 3, 3],
            "xywh": [1, 1, 2, 2],
            "normalized_xyxy": [1 / 6, 1 / 4, 3 / 6, 3 / 4],
            "normalized_xywh": [1 / 6, 1 / 4, 2 / 6, 2 / 4],
        }

        self.bbox_xyxy = BBox.from_xyxy(self.coords["xyxy"], confidence=0.5)
        self.bbox_xywh = BBox.from_xywh(self.coords["xywh"], confidence=None)

    def test_format(self):
        """Test BBox format property"""

        self.assertEqual(self.bbox_xyxy.format, "xyxy")
        self.assertEqual(self.bbox_xywh.format, "xywh")

    def test_is_normalized(self):
        """Test BBox is_normalized property"""

        self.assertTrue(self.bbox_xyxy.is_normalized)
        self.assertTrue(self.bbox_xywh.is_normalized)

    def test_is_predicted(self):
        """Test BBox is_predicted property"""

        self.assertTrue(self.bbox_xyxy.is_predicted)
        self.assertFalse(self.bbox_xywh.is_predicted)

    def test_xyxy_coords(self):
        """Test BBox xyxy_coords property"""

        converted_coords = self.bbox_xywh.xyxy_coords

        self.assertTrue(np.allclose(converted_coords, self.coords["xyxy"]))

    def test_xywh_coords(self):
        """Test BBox xywh_coords property"""

        converted_coords = self.bbox_xyxy.xywh_coords

        self.assertTrue(np.allclose(converted_coords, self.coords["xywh"]))

    def test_format_conversion(self):
        """Test BBox to_xywh and to_xyxy methods"""

        converted_xywh_bbox = self.bbox_xyxy.to_xywh()

        self.assertEqual(converted_xywh_bbox.format, "xywh")
        self.assertTrue(
            np.allclose(converted_xywh_bbox.xywh_coords, self.coords["xywh"])
        )

        converted_xyxy_bbox = self.bbox_xywh.to_xyxy()

        self.assertEqual(converted_xyxy_bbox.format, "xyxy")
        self.assertTrue(
            np.allclose(converted_xyxy_bbox.xyxy_coords, self.coords["xyxy"])
        )

    def test_normalization(self):
        """Test BBox normalize and denormalize methods"""

        normalized_bbox = self.bbox_xyxy.normalize(self.height, self.width)

        self.assertTrue(
            np.allclose(normalized_bbox.xyxy_coords, self.coords["normalized_xyxy"])
        )

        denormalized_bbox = normalized_bbox.denormalize(self.height, self.width)

        self.assertTrue(np.allclose(denormalized_bbox.xyxy_coords, self.coords["xyxy"]))


class TestParquetBBox(unittest.TestCase):
    """BBox test case for Parquet storage"""

    def setUp(self):
        """Tests setup"""

        self.bbox_list = [
            BBox.from_xywh([0.1, 0.2, 0.3, 0.4], confidence=0.3),
            BBox.from_xyxy([0.1, 0.2, 0.2, 0.2], confidence=0.4),
        ]

    def test_bbox_table(self):
        """Test BBox Parquet storage"""

        bbox_arr = BBoxType.Array.from_pylist(self.bbox_list)
        table = pa.Table.from_arrays(
            [bbox_arr],
            schema=pa.schema([pa.field("bbox", BBoxType)]),
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["bbox"])

        bbox_0 = re_table.to_pylist()[0]["bbox"]

        self.assertTrue(isinstance(bbox_0, BBox))
        self.assertTrue(np.allclose(self.bbox_list[0].xyxy_coords, bbox_0.xyxy_coords))
