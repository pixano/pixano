# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.features.types.schema_reference import (
    AnnotationRef,
    EmbeddingRef,
    EntityRef,
    ItemRef,
    SchemaRef,
    SourceRef,
    ViewRef,
)


class TestSchemaReference:
    def test_none(self):
        assert SchemaRef.none() == SchemaRef(name="", id="")

    def test_resolve(self, dataset_image_bboxes_keypoint):
        schema_ref = SchemaRef(name="item", id="0")
        assert schema_ref.resolve(dataset_image_bboxes_keypoint) == dataset_image_bboxes_keypoint.resolve_ref(
            schema_ref
        )


class TestItemRef:
    def test_init(self):
        item_ref = ItemRef()
        assert item_ref.name == "item"
        assert item_ref.id == ""

    def test_validate_fields(self):
        with pytest.raises(ValueError, match="name must be 'item' when not empty."):
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


class TestSourceRef:
    def test_init(self):
        source_ref = SourceRef()
        assert source_ref.name == "source"
        assert source_ref.id == ""

    def test_validate_fields(self):
        with pytest.raises(ValueError, match="name must be 'source' when not empty."):
            SourceRef(name="yolo", id="")
