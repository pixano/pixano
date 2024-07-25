# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features import Embedding, is_embedding
from pixano.datasets.features.types.schema_reference import ItemRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


class TestEmbedding:
    def test_init(self):
        embedding = Embedding()
        embedding.id == ""
        embedding.item_ref == ItemRef.none()


def test_is_embedding():
    make_tests_is_sublass_strict(is_embedding, Embedding)
