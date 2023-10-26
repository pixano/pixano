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

from pixano.core.bbox import BBox, BBoxType


class BBoxTestCase(unittest.TestCase):
    def setUp(self):
        self.height = 4
        self.width = 6
        self.xyxy = [1, 1, 3, 3]
        self.xywh = [1, 1, 2, 2]
        self.normalized_xyxy = [1 / 6, 1 / 4, 3 / 6, 3 / 4]
        self.normalized_xywh = [1 / 6, 1 / 4, 2 / 6, 2 / 4]
        self.bbox_xyxy = BBox.from_xyxy(self.xyxy, confidence=0.5)
        self.bbox_xywh = BBox.from_xywh(self.xywh, confidence=None)

    def test_format_property(self):
        self.assertEqual(self.bbox_xyxy.format, "xyxy")
        self.assertEqual(self.bbox_xywh.format, "xywh")

    def test_is_normalized_property(self):
        self.assertTrue(self.bbox_xyxy.is_normalized)
        self.assertTrue(self.bbox_xywh.is_normalized)

    def test_is_predicted_property(self):
        self.assertTrue(self.bbox_xyxy.is_predicted)
        self.assertFalse(self.bbox_xywh.is_predicted)

    def test_xyxy_coords(self):
        converted_coords = self.bbox_xywh.xyxy_coords
        self.assertTrue(np.allclose(converted_coords, self.xyxy))

    def test_xywh_coords(self):
        converted_coords = self.bbox_xyxy.xywh_coords
        self.assertTrue(np.allclose(converted_coords, self.xywh))

    def test_format_conversion(self):
        converted_xywh_bbox = self.bbox_xyxy.to_xywh()
        self.assertEqual(converted_xywh_bbox.format, "xywh")
        self.assertTrue(np.allclose(converted_xywh_bbox.xywh_coords, self.xywh))

        converted_xyxy_bbox = self.bbox_xywh.to_xyxy()
        self.assertEqual(converted_xyxy_bbox.format, "xyxy")
        self.assertTrue(np.allclose(converted_xyxy_bbox.xyxy_coords, self.xyxy))

    def test_normalization(self):
        normalized_bbox = self.bbox_xyxy.normalize(self.height, self.width)
        self.assertTrue(np.allclose(normalized_bbox.xyxy_coords, self.normalized_xyxy))

        denormalized_bbox = normalized_bbox.denormalize(self.height, self.width)
        self.assertTrue(np.allclose(denormalized_bbox.xyxy_coords, self.xyxy))


class TestParquetBBox(unittest.TestCase):
    def setUp(self) -> None:
        self.bbox_list = [
            BBox.from_xywh([0.1, 0.2, 0.3, 0.4], confidence=0.3),
            BBox.from_xyxy([0.1, 0.2, 0.2, 0.2], confidence=0.4),
        ]

    def test_bbox_table(self):
        bbox_arr = BBoxType.Array.from_pylist(self.bbox_list)

        table = pa.Table.from_arrays(
            [bbox_arr], schema=pa.schema([pa.field("bbox", BBoxType)])
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)
        self.assertEqual(re_table.column_names, ["bbox"])
        Bbox0 = re_table.to_pylist()[0]["bbox"]
        self.assertTrue(isinstance(Bbox0, BBox))
        self.assertTrue(np.allclose(self.bbox_list[0].xyxy_coords, Bbox0.xyxy_coords))
