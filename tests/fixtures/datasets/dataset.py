# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest

from tests.fixtures.datasets.builders import builder as fixture_builder


dumb_builder = fixture_builder.dumb_builder


@pytest.fixture
def dumb_dataset(dumb_builder):
    return dumb_builder.build()
