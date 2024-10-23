# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json

import numpy as np
import pytest
from pydantic_core._pydantic_core import ValidationError

from pixano.features import Classification, create_classification, is_classification
from pixano.features.types.schema_reference import AnnotationRef, EntityRef, ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


class TestClassification:
    def test_constructor(self):
        with pytest.raises(ValidationError):
            Classification()
        with pytest.raises(ValidationError):
            Classification(labels=["abc"])
        with pytest.raises(ValidationError):
            Classification(confidences=[1.0])
        with pytest.raises(ValidationError):
            Classification(labels=["abd", "def"], confidences=[1.0])

    def test_none(self):
        none_ne = Classification.none()
        assert none_ne.id == ""
        assert none_ne.item_ref == ItemRef.none()
        assert none_ne.view_ref == ViewRef.none()
        assert none_ne.entity_ref == EntityRef.none()
        assert none_ne.labels == []
        assert none_ne.confidences == []
        assert list(none_ne.predictions) == []


def test_is_classification():
    make_tests_is_sublass_strict(is_classification, Classification)


def test_create_classification():
    # Test 1: default references
    cla = create_classification(labels=["abc", "def"], confidences=[1.0, 0.5])
    assert isinstance(cla, Classification)
    assert list(cla.predictions) == [("abc", 1.0), ("def", 0.5)]
    assert cla.id == ""
    assert cla.item_ref == ItemRef.none()
    assert cla.view_ref == ViewRef.none()
    assert cla.entity_ref == EntityRef.none()

    # Test 2: with references
    cla = create_classification(
        labels=["abc", "def"],
        confidences=[1.0, 0.5],
        id="cla_1",
        item_ref=ItemRef(id="item_1"),
        view_ref=ViewRef(id="view_1", name="text"),
        entity_ref=EntityRef(id="entity_1", name="entity"),
    )
    assert isinstance(cla, Classification)
    assert list(cla.predictions) == [("abc", 1.0), ("def", 0.5)]
    assert cla.id == "cla_1"
    assert cla.item_ref == ItemRef(id="item_1")
    assert cla.view_ref == ViewRef(id="view_1", name="text")
    assert cla.entity_ref == EntityRef(id="entity_1", name="entity")
