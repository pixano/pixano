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

from pixano.utils import (
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)

from pixano.core.compressed_rle import CompressedRLE, CompressedRLEType


class CompressedRLETestCase(unittest.TestCase):
    def setUp(self):
        self.size = [10, 10]
        self.counts = bytes(b";37000k1")
        self.rle = CompressedRLE(self.size, self.counts)

    def test_from_dict(self):
        rle_dict = {"size": self.size, "counts": self.counts}
        rle = CompressedRLE.from_dict(rle_dict)
        self.assertEqual(rle.size, self.size)
        self.assertEqual(rle.counts, self.counts)

    def test_to_dict(self):
        rle_dict = self.rle.to_dict()
        self.assertEqual(rle_dict["size"], self.size)
        self.assertEqual(rle_dict["counts"], self.counts)

    def test_to_mask(self):
        mask = self.rle.to_mask()
        expected_mask = rle_to_mask(self.rle.to_dict())
        self.assertIsInstance(mask, np.ndarray)
        self.assertEqual(mask.tolist(), expected_mask.tolist())

    def test_to_urle(self):
        urle = self.rle.to_urle()
        expected_urle = rle_to_urle(self.rle.to_dict())
        self.assertEqual(urle, expected_urle)

    def test_to_polygons(self):
        polygons = self.rle.to_polygons()
        expected_polygons = rle_to_polygons(self.rle.to_dict())
        self.assertEqual(polygons, expected_polygons)

    def test_from_mask(self):
        mask = np.ndarray((10, 10), dtype=bool)
        rle = CompressedRLE.from_mask(mask)
        expected_rle_dict = mask_to_rle(mask)
        expected_rle = CompressedRLE.from_dict(expected_rle_dict)
        self.assertEqual(rle.size, expected_rle.size)
        self.assertEqual(rle.counts, expected_rle.counts)

    def test_from_urle(self):
        urle = {"counts": [1, 2, 3, 2, 4, 1], "size": [10, 10]}
        rle = CompressedRLE.from_urle(urle)
        expected_rle_dict = urle_to_rle(urle)
        expected_rle = CompressedRLE.from_dict(expected_rle_dict)
        self.assertEqual(rle.size, expected_rle.size)
        self.assertEqual(rle.counts, expected_rle.counts)

    def test_from_polygons(self):
        polygons = [[1, 1, 2, 2, 2, 1], [3, 3, 4, 4, 4, 3]]
        height, width = 10, 10
        rle = CompressedRLE.from_polygons(polygons, height, width)
        expected_rle_dict = polygons_to_rle(polygons, height, width)
        expected_rle = CompressedRLE.from_dict(expected_rle_dict)
        self.assertEqual(rle.size, expected_rle.size)
        self.assertEqual(rle.counts, expected_rle.counts)


class TestParquetCompressedRLE(unittest.TestCase):
    def setUp(self) -> None:
        self.compressedRLE_list = [
            CompressedRLE([1, 2], None),
            CompressedRLE([1, 2], None),
        ]

    def test_compressedRLE_table(self):
        compressedRLE_array = CompressedRLEType.Array.from_pylist(
            self.compressedRLE_list
        )

        schema = pa.schema(
            [
                pa.field("compressedRLE", CompressedRLEType),
            ]
        )

        table = pa.Table.from_arrays([compressedRLE_array], schema=schema)

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["compressedRLE"])
        compressedRLE1 = re_table.take([0])["compressedRLE"][0].as_py()
        self.assertTrue(isinstance(compressedRLE1, CompressedRLE))
