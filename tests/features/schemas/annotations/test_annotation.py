# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import Annotation, is_annotation
from pixano.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


class TestAnnotation:
    def test_init(self):
        annotation = Annotation()
        annotation == Annotation(
            id="",
            item_ref=ItemRef.none(),
            entity_ref=EntityRef.none(),
        )


def test_is_annotation():
    make_tests_is_sublass_strict(is_annotation, Annotation)
