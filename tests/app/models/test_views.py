# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import TableInfo, ViewModel
from pixano.features import Item, View


class TestViewModel:
    def test_to_row(self):
        table_info = TableInfo(name="view", group="views", base_schema="View")
        model = ViewModel(
            id="id",
            table_info=table_info,
            data={
                "item_ref": {"id": "", "name": ""},
                "parent_ref": {"id": "", "name": ""},
            },
        )
        view = model.to_row(View)

        assert view == View(
            id="id",
            item_ref={"id": "", "name": ""},
            view_ref={"id": "", "name": ""},
            parent_ref={"id": "", "name": ""},
        )

        with pytest.raises(ValueError, match="Schema type must be a subclass of View."):
            model.to_row(Item)
