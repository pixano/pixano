# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pixano.features import CompressedRLE, CompressedRLEType
from pixano.utils import (
    mask_to_rle,
    polygons_to_rle,
    rle_to_mask,
    rle_to_polygons,
    rle_to_urle,
    urle_to_rle,
)


class CompressedRLETestCase(unittest.TestCase):
    """CompressedRLE test case"""

    def setUp(self):
        """Tests setup"""

        self.size = [10, 10]
        self.counts = bytes(b";37000k1")
        self.rle = CompressedRLE(self.size, self.counts)

    def test_from_dict(self):
        """Test CompressedRLE from_dict method"""

        rle_dict = {"size": self.size, "counts": self.counts}
        rle = CompressedRLE.from_dict(rle_dict)

        self.assertEqual(rle.size, self.size)
        self.assertEqual(rle.counts, self.counts)

    def test_to_dict(self):
        """Test CompressedRLE to_dict method"""

        rle_dict = self.rle.to_dict()

        self.assertEqual(rle_dict["size"], self.size)
        self.assertEqual(rle_dict["counts"], self.counts)

    def test_to_mask(self):
        """Test CompressedRLE to_mask method"""

        mask = self.rle.to_mask()
        expected_mask = rle_to_mask(self.rle.to_dict())

        self.assertIsInstance(mask, np.ndarray)
        self.assertEqual(mask.tolist(), expected_mask.tolist())

    def test_to_urle(self):
        """Test CompressedRLE to_urle method"""

        urle = self.rle.to_urle()
        expected_urle = rle_to_urle(self.rle.to_dict())

        self.assertEqual(urle, expected_urle)

    def test_to_polygons(self):
        """Test CompressedRLE to_polygons method"""

        polygons = self.rle.to_polygons()
        expected_polygons = rle_to_polygons(self.rle.to_dict())

        self.assertEqual(polygons, expected_polygons)

    def test_from_mask(self):
        """Test CompressedRLE from_mask method"""

        mask = np.ndarray((10, 10), dtype=bool)
        rle = CompressedRLE.from_mask(mask)
        expected_rle_dict = mask_to_rle(mask)
        expected_rle = CompressedRLE.from_dict(expected_rle_dict)

        self.assertEqual(rle.size, expected_rle.size)
        self.assertEqual(rle.counts, expected_rle.counts)

    def test_from_urle(self):
        """Test CompressedRLE from_urle method"""

        urle = {"counts": [1, 2, 3, 2, 4, 1], "size": [10, 10]}
        rle = CompressedRLE.from_urle(urle)
        expected_rle_dict = urle_to_rle(urle)
        expected_rle = CompressedRLE.from_dict(expected_rle_dict)

        self.assertEqual(rle.size, expected_rle.size)
        self.assertEqual(rle.counts, expected_rle.counts)

    def test_from_polygons(self):
        """Test CompressedRLE from_polygons method"""

        polygons = [[1, 1, 2, 2, 2, 1], [3, 3, 4, 4, 4, 3]]
        height, width = 10, 10
        rle = CompressedRLE.from_polygons(polygons, height, width)
        expected_rle_dict = polygons_to_rle(polygons, height, width)
        expected_rle = CompressedRLE.from_dict(expected_rle_dict)

        self.assertEqual(rle.size, expected_rle.size)
        self.assertEqual(rle.counts, expected_rle.counts)


class TestParquetCompressedRLE(unittest.TestCase):
    """CompressedRLE test case for Parquet storage"""

    def setUp(self):
        """Tests setup"""

        self.rle_list = [
            CompressedRLE([1, 2], None),
            CompressedRLE([1, 2], None),
        ]

    def test_compressed_rle_table(self):
        """Test CompressedRLE Parquet storage"""

        rle_arr = CompressedRLEType.Array.from_pylist(self.rle_list)
        table = pa.Table.from_arrays(
            [rle_arr],
            schema=pa.schema([pa.field("compressedRLE", CompressedRLEType)]),
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["compressedRLE"])

        rle_1 = re_table.take([0])["compressedRLE"][0].as_py()

        self.assertIsInstance(rle_1, CompressedRLE)
