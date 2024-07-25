# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features import Annotation, is_annotation
from pixano.datasets.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


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
