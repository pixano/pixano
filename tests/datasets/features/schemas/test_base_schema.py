# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.base_schema import BaseSchema, is_base_schema

from ..utils import make_tests_is_sublass_strict


def test_is_base_schema():
    make_tests_is_sublass_strict(is_base_schema, BaseSchema)
