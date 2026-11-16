# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Every vector of one model's embeddings, as the reader gives a kind that reads them all: the
records, their media and the vectors as the rows of a matrix."""

from types import SimpleNamespace

import numpy as np
import pyarrow as pa
from pixano_worker.media import MediaResolver
from pixano_worker.reader import JobReader


class TestRecordVectors:
    """Every vector of a dataset's embeddings, with its record and its medium, as a matrix."""

    def test_a_vector_left_empty_is_left_out(self) -> None:
        dim = 2
        table = pa.table(
            {
                "record_id": ["r1", "r2", "r3"],
                "view_id": ["v1", None, "v3"],
                "vector": pa.array([[1.0, 0.0], None, [0.0, 1.0]], pa.list_(pa.float32(), dim)),
            }
        )
        reader = JobReader(
            lambda: SimpleNamespace(read_record_vectors=lambda model=None: table), MediaResolver("/m", "/m")
        )

        vectors = reader.record_vectors()

        assert vectors is not None
        assert (vectors.record_ids, vectors.view_ids) == (["r1", "r3"], ["v1", "v3"])
        np.testing.assert_array_equal(vectors.vectors, [[1.0, 0.0], [0.0, 1.0]])

    def test_none_without_embeddings(self) -> None:
        reader = JobReader(
            lambda: SimpleNamespace(read_record_vectors=lambda model=None: None), MediaResolver("/m", "/m")
        )

        assert reader.record_vectors() is None
