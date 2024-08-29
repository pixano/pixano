# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import TableInfo


class TestTableInfo:
    def test_init(self):
        TableInfo(name="item", group="item", base_schema="Item")

    def test_init_invalid_group(self):
        with pytest.raises(ValueError, match="Group itemsss is not valid."):
            TableInfo(name="item", group="itemsss", base_schema="Item")

    def test_must_be_registered(self):
        with pytest.raises(ValueError, match="Schema ItemUnkown is not registered."):
            TableInfo(name="item", group="item", base_schema="ItemUnkown")
