# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json

import pytest

from pixano.features import Source, is_source
from pixano.features.schemas.source import create_source
from tests.features.utils import make_tests_is_sublass_strict


class TestSource:
    def test_init(self):
        metadata = json.dumps({"key": "value"})
        source = Source(name="source", kind="human", metadata=metadata)
        assert source.model_dump(exclude_timestamps=True) == Source(
            id="", name="source", kind="human", metadata=metadata
        ).model_dump(exclude_timestamps=True)

        source = Source(name="source", kind="human", metadata={"key": "value"})
        assert source.model_dump(exclude_timestamps=True) == Source(
            id="", name="source", kind="human", metadata=metadata
        ).model_dump(exclude_timestamps=True)

        with pytest.raises(ValueError):
            source = Source(kind="invalid")

        with pytest.raises(ValueError):
            source = Source(name="source", kind="ground-truth", metadata=12345)


def test_is_source():
    make_tests_is_sublass_strict(is_source, Source)


def test_create_source():
    source = Source(id="source_1", name="source", kind="human", metadata={"key": "value"})
    assert source.model_dump(exclude_timestamps=True) == create_source(
        id="source_1", name="source", kind="human", metadata=json.dumps({"key": "value"})
    ).model_dump(exclude_timestamps=True)