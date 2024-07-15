# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_info import DatasetInfo


@pytest.fixture
def info():
    return DatasetInfo(
        name="test",
        description="test",
    )
