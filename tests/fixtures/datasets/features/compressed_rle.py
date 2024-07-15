# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.features import CompressedRLE


@pytest.fixture()
def size():
    return [10, 10]


@pytest.fixture()
def counts():
    return bytes(b";37000k1")


@pytest.fixture()
def rle(size, counts):
    return CompressedRLE(size=size, counts=counts)
