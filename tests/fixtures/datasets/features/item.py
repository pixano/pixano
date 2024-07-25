# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest

from pixano.datasets.features.schemas import Item
from pixano.datasets.features.schemas.registry import register_schema


@pytest.fixture
def custom_item_1():
    class CustomItem(Item):
        categories: tuple[str, ...]
        other_categories: list[int]

    try:
        register_schema(CustomItem)
    except ValueError:
        pass
    return CustomItem


@pytest.fixture
def custom_item_2():
    class CustomItem(Item):
        categories: tuple[str, ...]
        other_categories: list[int]
        name: str
        index: int

    return CustomItem
