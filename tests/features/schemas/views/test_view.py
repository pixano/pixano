# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import View, is_view
from tests.features.utils import make_tests_is_sublass_strict


class TestView:
    def test_init(self):
        view = View()
        assert view.model_dump(exclude={"created_at", "updated_at"}) == View(
            id="",
            record_id="",
        ).model_dump(exclude={"created_at", "updated_at"})


def test_is_view():
    make_tests_is_sublass_strict(is_view, View)
