# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import patch

import pyarrow as pa
from lancedb.embeddings import EmbeddingFunction
from lancedb.embeddings.registry import get_registry
from lancedb.pydantic import FixedSizeListMixin, pydantic_to_schema
from numpy.core.multiarray import array as array

from pixano.datasets.dataset import Dataset
from pixano.features import (
    Embedding,
    ViewEmbedding,
    create_view_embedding_function,
    is_embedding,
    is_view_embedding,
)
from pixano.features.schemas.embeddings.embedding import _to_pixano_name
from pixano.features.types.schema_reference import ItemRef, ViewRef
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY
from tests.features.utils import make_tests_is_sublass_strict


@classmethod
def mock_super_to_arrow_schema(cls):
    schema = pydantic_to_schema(cls)
    schema = schema.with_metadata({"test": "metadata"})
    return schema


class TestEmbedding:
    def test_init(self, embedding_8: type[Embedding]):
        embedding = embedding_8(vector=[1, 2, 3, 4, 5, 6, 7, 8])
        assert embedding.id == ""
        assert embedding.item_ref == ItemRef.none()
        assert embedding.vector == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_to_arrow_schema(self, embedding_8):
        with patch("lancedb.pydantic.LanceModel.to_arrow_schema", mock_super_to_arrow_schema):
            arrow_schema = embedding_8.to_arrow_schema(remove_vector=False, remove_metadata=False)
            assert set(arrow_schema.names) == {"item_ref", "vector", "id", "created_at", "updated_at"}
            assert arrow_schema.metadata == {b"test": b"metadata"}

            arrow_schema = embedding_8.to_arrow_schema(remove_vector=True, remove_metadata=False)
            assert set(arrow_schema.names) == {"item_ref", "id", "created_at", "updated_at"}
            assert arrow_schema.metadata == {b"test": b"metadata"}

            arrow_schema = embedding_8.to_arrow_schema(remove_vector=False, remove_metadata=True)
            assert set(arrow_schema.names) == {"vector", "id", "item_ref", "created_at", "updated_at"}
            assert arrow_schema.metadata is None

    def test_create_shema(
        self, dumb_embedding_function: type[EmbeddingFunction], dataset_image_bboxes_keypoint_copy: Dataset
    ):
        registry = get_registry()
        registry._functions["test_create_shema_dumb_embedding_function"] = dumb_embedding_function

        assert (
            _to_pixano_name(
                dataset_image_bboxes_keypoint_copy,
                "test_create_shema_view_embedding",
                "test_create_shema_dumb_embedding_function",
            )
            not in registry._functions
        )

        schema = ViewEmbedding.create_schema(
            "test_create_shema_dumb_embedding_function",
            "test_create_shema_view_embedding",
            dataset_image_bboxes_keypoint_copy,
        )

        assert (
            _to_pixano_name(
                dataset_image_bboxes_keypoint_copy,
                "test_create_shema_view_embedding",
                "test_create_shema_dumb_embedding_function",
            )
            in registry._functions
        )
        assert issubclass(schema, ViewEmbedding)

        assert set(schema.model_fields) == {"id", "item_ref", "vector", "view_ref", "created_at", "updated_at"}
        assert schema.model_fields["id"].annotation is str
        assert schema.model_fields["id"].default == ""
        assert schema.model_fields["item_ref"].annotation == ItemRef
        assert schema.model_fields["item_ref"].default == ItemRef.none()
        assert issubclass(schema.model_fields["vector"].annotation, FixedSizeListMixin)
        assert "vector_column_for" in schema.model_fields["vector"].json_schema_extra and isinstance(
            schema.model_fields["vector"].json_schema_extra["vector_column_for"], EmbeddingFunction
        )
        assert schema.model_fields["view_ref"].annotation == ViewRef
        assert "source_column_for" in schema.model_fields["view_ref"].json_schema_extra and isinstance(
            schema.model_fields["view_ref"].json_schema_extra["source_column_for"], EmbeddingFunction
        )

        # Check that pixano function can be reused
        schema = ViewEmbedding.create_schema(
            "test_create_shema_dumb_embedding_function",
            "test_create_shema_view_embedding",
            dataset_image_bboxes_keypoint_copy,
        )


class TestViewEmbedding:
    def test_init(self, view_embedding_8: type[ViewEmbedding]):
        view_embedding = view_embedding_8(vector=[1, 2, 3, 4, 5, 6, 7, 8])
        assert view_embedding.id == ""
        assert view_embedding.item_ref == ItemRef.none()
        assert view_embedding.view_ref == ViewRef.none()
        assert view_embedding.vector == [1, 2, 3, 4, 5, 6, 7, 8]


def test_is_embedding():
    make_tests_is_sublass_strict(is_embedding, Embedding)


def test_is_view_embedding():
    make_tests_is_sublass_strict(is_view_embedding, ViewEmbedding)


class TestViewEmbeddingFunction:
    def test_create_view_embedding_function(
        self, dumb_embedding_function: type[EmbeddingFunction], dataset_image_bboxes_keypoint_copy: Dataset
    ):
        registry = get_registry()
        assert "test_view_embedding_fn" not in registry._functions
        view_embedding_fn = create_view_embedding_function(
            dumb_embedding_function, "test_view_embedding_fn", dataset_image_bboxes_keypoint_copy
        )
        assert "test_view_embedding_fn" in registry._functions

        assert view_embedding_fn.__name__ == "ViewEmbeddingFunction"
        assert issubclass(view_embedding_fn, dumb_embedding_function)

    def test_compute_source_embeddings(
        self, dumb_embedding_function: type[EmbeddingFunction], dataset_image_bboxes_keypoint_copy: Dataset
    ):
        view_embedding_fn_type = create_view_embedding_function(
            dumb_embedding_function, "test_view_embedding_fn", dataset_image_bboxes_keypoint_copy
        )
        view_embedding_fn = view_embedding_fn_type.create()

        views = dataset_image_bboxes_keypoint_copy.get_data("image", limit=2)
        for view in views:
            view.url = "file://" + str(ASSETS_DIRECTORY / "sample_data/image_jpg.jpg")
        dataset_image_bboxes_keypoint_copy.update_data("image", views)
        view_refs = pa.Table.from_pylist([ViewRef(id=view.id, name=view.table_name).model_dump() for view in views])
        embeddings = view_embedding_fn.compute_source_embeddings(view_refs)
        assert embeddings == [[1, 2, 3, 4, 5, 6, 7, 8]] * 2
