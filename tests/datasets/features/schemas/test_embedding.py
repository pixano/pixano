# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.embedding import Embedding, is_embedding
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_embedding():
    make_tests_is_sublass_strict(is_embedding, Embedding)
