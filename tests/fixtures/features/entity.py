# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest

from pixano.features.schemas import Entity
from tests.utils.schema import register_schema


@pytest.fixture()
def entity_category():
    class EntityCategory(Entity):
        category: str = "none"

    register_schema(EntityCategory)
    return EntityCategory
