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

from pixano.core.arrow_types.embedding import Embedding, EmbeddingType


class EmbeddingTestCase(unittest.TestCase):
    # TODO when more info on embedding
    pass


class TestParquetEmbedding(unittest.TestCase):
    def setUp(self) -> None:
        self.embedding_list = [Embedding(b"test_bytes1"), Embedding(b"test_bytes2")]

    def test_embeddin_table(self):
        embeddin_array = EmbeddingType.Array.from_list(self.embedding_list)

        schema = pa.schema(
            [
                pa.field("embedding", EmbeddingType),
            ]
        )

        table = pa.Table.from_arrays([embeddin_array], schema=schema)

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path, store_schema=True)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["embedding"])
        embeddin1 = re_table.take([1])["embedding"][0].as_py()
        self.assertTrue(isinstance(embeddin1, Embedding))
