# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest

from pixano.features.schemas import SequenceFrame
from tests.utils.schema import register_schema


@pytest.fixture()
def sequence_frame_category():
    class SequenceFrameCategory(SequenceFrame):
        category: str

    register_schema(SequenceFrameCategory)
    return SequenceFrameCategory
