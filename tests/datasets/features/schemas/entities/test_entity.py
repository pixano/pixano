# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features import Entity, is_entity
from pixano.datasets.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


class TestEntity:
    def test_init(self):
        entity = Entity()
        entity.id == ""
        entity.item_ref == ItemRef.none()
        entity.view_ref == ViewRef.none()
        entity.parent_ref == EntityRef.none()


def test_is_entity():
    make_tests_is_sublass_strict(is_entity, Entity)
