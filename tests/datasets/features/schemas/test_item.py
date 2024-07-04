# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.item import Item, is_item
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_item():
    make_tests_is_sublass_strict(is_item, Item)
