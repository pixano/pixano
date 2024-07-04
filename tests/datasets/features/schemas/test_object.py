# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.object import Object, is_object
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_object():
    make_tests_is_sublass_strict(is_object, Object)
