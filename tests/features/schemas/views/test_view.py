# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import View, is_view
from pixano.features.types.schema_reference import ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


class TestView:
    def test_init(self):
        view = View()
        assert view == View(
            id="",
            item_ref=ItemRef.none(),
            parent_ref=ViewRef.none(),
        )


def test_is_view():
    make_tests_is_sublass_strict(is_view, View)
