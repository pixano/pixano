# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.view import View, is_view
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_view():
    make_tests_is_sublass_strict(is_view, View)
