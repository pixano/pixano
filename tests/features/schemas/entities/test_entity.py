# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import Entity, is_entity
from tests.features.utils import make_tests_is_sublass_strict


class TestEntity:
    def test_init(self):
        entity = Entity()
        entity.id == ""
        entity.record_id == ""
        entity.parent_id == ""


def test_is_entity():
    make_tests_is_sublass_strict(is_entity, Entity)
