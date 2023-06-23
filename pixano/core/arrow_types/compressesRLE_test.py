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

from .compressedRLE import CompressedRLE, CompressedRLEArray, CompressedRLEType


class CompressedRLETestCase(unittest.TestCase):
    pass


class TestParquetCompressedRLE(unittest.TestCase):
    def setUp(self) -> None:
        self.compressedRLE_list = [
            CompressedRLE([1, 2], None),
            CompressedRLE([1, 2], None),
        ]

    def test_compressedRLE_table(self):
        compressedRLE_array = CompressedRLEArray.from_CompressedRLE_list(
            self.compressedRLE_list
        )

        schema = pa.schema(
            [
                pa.field("compressedRLE", CompressedRLEType()),
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
