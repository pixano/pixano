# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest
from pydantic import create_model

from pixano.features.schemas import Item
from tests.utils.schema import register_schema


@pytest.fixture(scope="session")
def item_metadata():
    item_metadata = create_model("Item", metadata=(str, ...), __base__=Item)
    return item_metadata


@pytest.fixture(scope="session")
def item_categories():
    class ItemCategories(Item):
        categories: tuple[str, ...]
        other_categories: list[int]

    register_schema(ItemCategories)
    return ItemCategories


@pytest.fixture(scope="session")
def item_categories_name_index():
    class ItemCategoriesNameIndex(Item):
        categories: tuple[str, ...]
        other_categories: list[int]
        name: str
        index: int

    register_schema(ItemCategoriesNameIndex)
    return ItemCategoriesNameIndex
