# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np
import pytest
from pydantic_core._pydantic_core import ValidationError

from pixano.features import NamedEntity, Relation, create_namedentity, create_relation, is_namedentity, is_relation
from pixano.features.types.schema_reference import AnnotationRef, EntityRef, ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


class TestNamedEntity:
    def test_constructor(self):
        with pytest.raises(ValidationError):
            NamedEntity()
        with pytest.raises(ValidationError):
            NamedEntity(concept_id="123")
        with pytest.raises(ValidationError):
            NamedEntity(concept_id="123", mention="abc")
        with pytest.raises(ValidationError):
            NamedEntity(concept_id="123", spans_start=[123], spans_end=[126])

    def test_spans_property(self):
        ne1 = NamedEntity(concept_id="123", spans_start=[123], spans_end=[126], mention="abc")
        assert list(ne1.spans) == [(123, 126)]

    def test_spans_property_on_disjoint_entity(self):
        ne2 = NamedEntity(concept_id="123", spans_start=[123, 131], spans_end=[126, 134], mention="abc def")
        assert list(ne2.spans) == [(123, 126), (131, 134)]
        assert ne2.spans_start == [123, 131]
        assert ne2.spans_end == [126, 134]
        assert list(ne2.spans_length) == [3, 3]

    def test_spans_property_on_ungrounded_entity(self):
        ne3 = NamedEntity(concept_id="123", spans_start=[], spans_end=[], mention="abc def")
        assert list(ne3.spans) == []
        assert list(ne3.spans_length) == []

    def test_none(self):
        none_ne = NamedEntity.none()
        assert none_ne.id == ""
        assert none_ne.item_ref == ItemRef.none()
        assert none_ne.view_ref == ViewRef.none()
        assert none_ne.entity_ref == EntityRef.none()
        assert none_ne.concept_id == ""
        assert none_ne.mention == ""
        assert list(none_ne.spans) == []


class TestRelation:
    def test_constructor(self):
        with pytest.raises(ValidationError):
            Relation()
        with pytest.raises(ValidationError):
            Relation(predicate_id="123")
        with pytest.raises(ValidationError):
            Relation(predicate_id="123", subject_id=AnnotationRef(id="456", name="named_entities"))
        with pytest.raises(ValidationError):
            Relation(predicate_id="123", object_id=AnnotationRef(id="789", name="named_entities"))

    def test_references(self):
        ne1 = NamedEntity(concept_id="123", spans_start=[123], spans_end=[126], mention="abc", id="ne1")
        ne2 = NamedEntity(concept_id="456", spans_start=[128], spans_end=[131], mention="def", id="ne2")
        rel = Relation(
            predicate_id="ad-hoc",
            subject_id=AnnotationRef(id=ne1.id, name="named_entities"),
            object_id=AnnotationRef(id=ne2.id, name="named_entities"),
        )

        assert rel.predicate_id == "ad-hoc"
        assert isinstance(rel.subject_id, AnnotationRef)
        assert isinstance(rel.object_id, AnnotationRef)
        assert rel.subject_id.id == "ne1"
        assert rel.object_id.id == "ne2"
        assert rel.subject_id.name == "named_entities"
        assert rel.object_id.name == "named_entities"

    def test_none(self):
        none_rel = Relation.none()

        assert none_rel.id == ""
        assert none_rel.item_ref == ItemRef.none()
        assert none_rel.view_ref == ViewRef.none()
        assert none_rel.entity_ref == EntityRef.none()
        assert none_rel.predicate_id == ""
        assert none_rel.subject_id == AnnotationRef.none()
        assert none_rel.object_id == AnnotationRef.none()


def test_is_namedentity():
    make_tests_is_sublass_strict(is_namedentity, NamedEntity)


def test_is_relation():
    make_tests_is_sublass_strict(is_relation, Relation)


def test_create_namedentiy():
    # Test 1: default references
    ne = create_namedentity(concept_id="123", spans_start=[123], spans_end=[126], mention="abc")
    assert isinstance(ne, NamedEntity)
    assert ne.concept_id == "123"
    assert ne.mention == "abc"
    assert list(ne.spans) == [(123, 126)]
    assert ne.id == ""
    assert ne.item_ref == ItemRef.none()
    assert ne.view_ref == ViewRef.none()
    assert ne.entity_ref == EntityRef.none()

    # Test 2: with references
    ne = create_namedentity(
        concept_id="123",
        spans_start=[123],
        spans_end=[126],
        mention="abc",
        id="ne_1",
        item_ref=ItemRef(id="item_1"),
        view_ref=ViewRef(id="view_1", name="text"),
        entity_ref=EntityRef(id="entity_1", name="entity"),
    )
    assert isinstance(ne, NamedEntity)
    assert ne.concept_id == "123"
    assert ne.mention == "abc"
    assert list(ne.spans) == [(123, 126)]
    assert ne.id == "ne_1"
    assert ne.item_ref == ItemRef(id="item_1")
    assert ne.view_ref == ViewRef(id="view_1", name="text")
    assert ne.entity_ref == EntityRef(id="entity_1", name="entity")


def test_create_relation():
    # Test 1: default references
    rel = create_relation(
        predicate_id="ad-hoc",
        subject_id=AnnotationRef(id="ne1", name="named_entities"),
        object_id=AnnotationRef(id="ne2", name="named_entities"),
    )
    assert isinstance(rel, Relation)
    assert rel.predicate_id == "ad-hoc"
    assert rel.subject_id == AnnotationRef(id="ne1", name="named_entities")
    assert rel.object_id == AnnotationRef(id="ne2", name="named_entities")
    assert rel.id == ""
    assert rel.item_ref == ItemRef.none()
    assert rel.view_ref == ViewRef.none()
    assert rel.entity_ref == EntityRef.none()

    # Test 2: with references
    rel = create_relation(
        predicate_id="ad-hoc",
        subject_id=AnnotationRef(id="ne1", name="named_entities"),
        object_id=AnnotationRef(id="ne2", name="named_entities"),
        id="rel_1",
        item_ref=ItemRef(id="item_1"),
        view_ref=ViewRef(id="view_1", name="text"),
        entity_ref=EntityRef(id="entity_1", name="entity"),
    )

    assert isinstance(rel, Relation)
    assert rel.predicate_id == "ad-hoc"
    assert rel.subject_id == AnnotationRef(id="ne1", name="named_entities")
    assert rel.object_id == AnnotationRef(id="ne2", name="named_entities")
    assert rel.id == "rel_1"
    assert rel.item_ref == ItemRef(id="item_1")
    assert rel.view_ref == ViewRef(id="view_1", name="text")
    assert rel.entity_ref == EntityRef(id="entity_1", name="entity")
