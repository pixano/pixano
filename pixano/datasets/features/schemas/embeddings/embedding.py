# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from abc import ABC
from typing import TYPE_CHECKING, Any, cast

import pyarrow as pa
from lancedb.embeddings import EmbeddingFunction
from lancedb.embeddings.registry import get_registry, register
from lancedb.pydantic import Vector
from pydantic import create_model

from pixano.datasets.features.schemas.views.image import Image, is_image
from pixano.datasets.features.schemas.views.sequence_frame import is_sequence_frame
from pixano.datasets.utils.python import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


if TYPE_CHECKING:
    from pixano.datasets.dataset import Dataset


def _to_pixano_name(dataset: "Dataset", table_name: str, name: str) -> str:
    return f"pixano_{dataset.info.id}_{table_name}_{name}"


def _from_pixano_name(dataset: "Dataset", table_name: str, pixano_name: str) -> str:
    return pixano_name[len(f"pixano_{dataset.info.id}_{table_name}_") :]


@_register_schema_internal
class Embedding(BaseSchema, ABC):
    """Embedding Lance Model.

    Attributes:
        item_ref (ItemRef, optional): Reference to the embedding's item.
        vector (Any): The embedding vector that should be defined by the embedding function.
    """

    item_ref: ItemRef = ItemRef.none()
    vector: Any  # TODO: change to Vector exposed parametrized type when LanceDB is updated

    @property
    def item(self):
        """Get the item."""
        return self.item_ref.resolve()

    @classmethod
    def to_arrow_schema(
        cls,
        remove_vector: bool = False,
        remove_metadata: bool = False,
    ) -> pa.Schema:
        """Get the pyarrow schema of a ViewEmbedding.

        This function allows to remove the vector field and the metadata from the schema which can be useful for adding
        data with auto-vectorization.

        Args:
            remove_vector (bool, optional): Remove the vector field.
            remove_metadata (bool, optional): Remove the metadata.

        Returns:
            pa.Schema: The pyarrow schema
        """
        pa_schema = super().to_arrow_schema()
        if remove_vector:
            pa_schema = pa_schema.remove(pa_schema.get_field_index("vector"))
        if remove_metadata:
            pa_schema = pa_schema.remove_metadata()
        return pa_schema


@_register_schema_internal
class ViewEmbedding(Embedding, ABC):
    """ViewEmbedding Lance Model.

    Attributes:
        view_ref (ItemRef, optional): Reference to the embedding's view.
    """

    view_ref: ViewRef = ViewRef.none()

    @property
    def view(self):
        """Get the item."""
        return self.resolve_ref(self.view_ref)

    @staticmethod
    def get_embedding_fn_from_table(dataset: "Dataset", table_name: str, metadata: dict) -> EmbeddingFunction:
        """Get the embedding function from a table.

        Args:
            dataset: The dataset containing the table.
            table_name: The name of the table containing the embedding function.
            metadata: The pyarrow metadata of the table.

        Returns:
            EmbeddingFunction: The embedding function.
        """
        registry = get_registry()

        serialized = metadata[b"embedding_functions"]
        raw_list = json.loads(serialized.decode("utf-8"))

        if len(raw_list) > 1:
            raise ValueError("Only one embedding function per table is supported")

        pixano_name = raw_list[0]["name"]
        if pixano_name not in registry._functions:
            name = _from_pixano_name(dataset, table_name, pixano_name)
            create_view_embedding_function(registry._functions[name], pixano_name, dataset)
        return registry.get(pixano_name)

    @classmethod
    def create_schema(
        cls,
        embedding_fn: str,
        table_name: str,
        dataset: "Dataset",
        **embedding_function_kwargs,
    ) -> type["ViewEmbedding"]:
        """Create a ViewEmbedding schema.

        Args:
            embedding_fn (EmbeddingFunction): The embedding function.
            table_name (str): The name of the table containing the schema.
            dataset (Dataset): The dataset to which the schema belongs.
            embedding_function_kwargs: The keyword arguments for creating the embedding function.

        Returns:
            type[ViewEmbedding]: The ViewEmbedding schema.
        """
        lance_registry = get_registry()
        if not isinstance(embedding_fn, str):
            raise TypeError(f"{embedding_fn} should be a string")

        pixano_name = _to_pixano_name(dataset, table_name, embedding_fn)
        if pixano_name not in lance_registry._functions:
            type_embedding_function = lance_registry.get(embedding_fn)
            view_embedding_function: type[EmbeddingFunction] = create_view_embedding_function(
                type_embedding_function, pixano_name, dataset
            )
        else:
            view_embedding_function = lance_registry.get(pixano_name)

        view_embedding_function = view_embedding_function.create(**embedding_function_kwargs)

        embedding_fields = {
            "vector": (Vector(view_embedding_function.ndims()), view_embedding_function.VectorField()),
            "view_ref": (ViewRef, view_embedding_function.SourceField()),
        }
        return create_model(
            "ViewEmbedding",
            __base__=ViewEmbedding,
            **embedding_fields,
        )


def is_embedding(cls: type, strict: bool = False) -> bool:
    """Check if a class is an Embedding or subclass of Embedding."""
    return issubclass_strict(cls, Embedding, strict)


def is_view_embedding(cls: type, strict: bool = False) -> bool:
    """Check if a class is an ViewEmbedding or subclass of ViewEmbedding."""
    return issubclass_strict(cls, ViewEmbedding, strict)


def create_view_embedding_function(
    type_embedding_function: type[EmbeddingFunction], name: str, dataset: "Dataset"
) -> type[EmbeddingFunction]:
    """Create a ViewEmbeddingFunction based on an EmbeddingFunction."""

    @register(name)
    class ViewEmbeddingFunction(type_embedding_function):
        """Create a ViewEmbeddingFunction based on an EmbeddingFunction."""

        def compute_source_embeddings(self, view_refs: pa.Table, *args, **kwargs) -> list:
            """Compute the embeddings for the source column in the database."""
            views = [dataset.resolve_ref(ViewRef(**view_ref)) for view_ref in view_refs.to_pylist()]
            view_type = type(views[0])
            if is_image(view_type) or is_sequence_frame(view_type):
                views = cast(list[Image], views)
                return super().compute_source_embeddings(
                    [view.open(dataset.media_dir, "image") for view in views], *args, **kwargs
                )
            else:
                raise ValueError(f"View type {view_type} not supported for embedding.")

    return ViewEmbeddingFunction
