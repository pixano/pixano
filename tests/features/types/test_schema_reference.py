# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.features.types.schema_reference import AnnotationRef, EmbeddingRef, EntityRef, ItemRef, SchemaRef, ViewRef


class TestSchemaReference:
    def test_none(self):
        assert SchemaRef.none() == SchemaRef(name="", id="")

    def test_resolve(self, dumb_dataset):
        schema_ref = SchemaRef(name="item", id="0")
        assert schema_ref.resolve(dumb_dataset) == dumb_dataset.resolve_ref(schema_ref)


class TestItemRef:
    def test_init(self):
        item_ref = ItemRef()
        assert item_ref.name == "item"
        assert item_ref.id == ""

    def test_validate_fields(self):
        with pytest.raises(ValueError, match="Schema must be 'item' when not empty."):
            ItemRef(name="yolo", id="")


class TestViewRef:
    def test_init(self):
        ViewRef(name="view", id="1")


class TestEntityRef:
    def test_init(self):
        EntityRef(name="entity", id="2")


class TestAnnotationRef:
    def test_init(self):
        AnnotationRef(name="annotation", id="3")


class TestEmbeddingRef:
    def test_init(self):
        EmbeddingRef(name="embedding", id="4")
