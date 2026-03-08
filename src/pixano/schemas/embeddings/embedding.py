# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
import json
from abc import ABC
from math import prod
from typing import TYPE_CHECKING, Any, cast
import pyarrow as pa
from lancedb.embeddings import EmbeddingFunction
from lancedb.embeddings.registry import get_registry, register
from lancedb.pydantic import Vector
from pydantic import create_model, model_validator
from typing_extensions import Self
from ..views.image import Image, is_image
from ..views.sequence_frame import is_sequence_frame
from pixano.utils import issubclass_strict
from ..records import RecordComponent

if TYPE_CHECKING:
    from pixano.datasets.dataset import Dataset


def _to_pixano_name(dataset: "Dataset", table_name: str, name: str) -> str:
    return f"pixano_{dataset.info.id}_{table_name}_{name}"


def _from_pixano_name(dataset: "Dataset", table_name: str, pixano_name: str) -> str:
    return pixano_name[len(f"pixano_{dataset.info.id}_{table_name}_") :]


class Embedding(RecordComponent, ABC):
    """Embeddings are used to define an embedding vector for a record in a dataset.
    Attributes:
        view_id: ID of the view this embedding is associated with.
        frame_id: ID of the view row used for this embedding.
        vector: The embedding vector that should be defined by subclasses.
    """

    view_id: str = ""
    frame_id: str = ""
    vector: Any  # TODO: change to Vector exposed parametrized type when LanceDB is updated
    shape: list[int] = []

    @model_validator(mode="after")
    def _validate_vector(self) -> Self:
        if self.shape == []:
            self.shape = [len(self.vector)]
        if prod(self.shape) != len(self.vector):
            raise ValueError("The vector shape does not match the specified shape.")
        return self

    @classmethod
    def to_arrow_schema(
        cls,
        remove_vector: bool = False,
        remove_metadata: bool = False,
    ) -> pa.Schema:
        """Get the pyarrow schema of an `Embedding`.
        This function allows to remove the vector field and the metadata from the schema which can be useful for adding
        data with auto-vectorization.
        Args:
            remove_vector: Remove the vector field.
            remove_metadata: Remove the metadata.
        Returns:
            The pyarrow schema.
        """
        pa_schema = super().to_arrow_schema()
        if remove_vector:
            pa_schema = pa_schema.remove(pa_schema.get_field_index("vector"))
        if remove_metadata:
            pa_schema = pa_schema.remove_metadata()
        return pa_schema


class ViewEmbedding(Embedding, ABC):
    """ViewEmbeddings are used to define an embedding vector for a view in a dataset.
    Attributes:
        frame_id: ID of the media row used as embedding source.
    """

    @staticmethod
    def get_embedding_fn_from_table(dataset: "Dataset", table_name: str, metadata: dict) -> EmbeddingFunction:
        """Get the embedding function from a table.
        Args:
            dataset: The dataset containing the table.
            table_name: The name of the table containing the embedding function.
            metadata: The pyarrow metadata of the table.
        Returns:
            The embedding function.
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
        **embedding_function_kwargs: Any,
    ) -> type["ViewEmbedding"]:
        """Create a ViewEmbedding schema.
        Args:
            embedding_fn: The embedding function.
            table_name: The name of the table containing the schema.
            dataset: The dataset to which the schema belongs.
            embedding_function_kwargs: The keyword arguments for creating the embedding function.
        Returns:
            The `ViewEmbedding` schema.
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
            "frame_id": (str, view_embedding_function.SourceField()),
        }
        return create_model(
            "ViewEmbedding",
            __base__=ViewEmbedding,
            **embedding_fields,
        )


def is_embedding(cls: type, strict: bool = False) -> bool:
    """Check if a class is an `Embedding` or subclass of `Embedding`."""
    return issubclass_strict(cls, Embedding, strict)


def is_view_embedding(cls: type, strict: bool = False) -> bool:
    """Check if a class is an `ViewEmbedding` or subclass of `ViewEmbedding`."""
    return issubclass_strict(cls, ViewEmbedding, strict)


def create_view_embedding_function(
    type_embedding_function: type[EmbeddingFunction], name: str, dataset: "Dataset"
) -> type[EmbeddingFunction]:
    """Create a `ViewEmbeddingFunction` based on an
    [EmbeddingFunction][lancedb.embeddings.base.EmbeddingFunction].
    """

    @register(name)
    class ViewEmbeddingFunction(type_embedding_function):
        """A `ViewEmbeddingFunction` based on an [EmbeddingFunction][lancedb.embeddings.base.EmbeddingFunction]."""

        def _open_views(self, views: list[Any]) -> list[Any]:
            """Open the views in the dataset."""
            return [view.open(dataset.media_dir, "image") for view in views]

        def compute_source_embeddings(
            self, frame_ids: pa.Table | pa.Array | pa.ChunkedArray | list[str], *args, **kwargs
        ) -> list:
            """Compute the embeddings for the source column in the database."""
            if hasattr(frame_ids, "to_pylist"):
                raw_frame_ids = frame_ids.to_pylist()
            else:
                raw_frame_ids = list(frame_ids)
            normalized_frame_ids: list[str] = []
            for row in raw_frame_ids:
                if isinstance(row, str):
                    normalized_frame_ids.append(row)
                    continue
                if isinstance(row, dict):
                    if "frame_id" in row and isinstance(row["frame_id"], str):
                        normalized_frame_ids.append(row["frame_id"])
                        continue
                    if len(row) == 1:
                        value = next(iter(row.values()))
                        if isinstance(value, str):
                            normalized_frame_ids.append(value)
                            continue
                raise ValueError(f"Unsupported source row for embedding: {row!r}")
            views = []
            for frame_id in normalized_frame_ids:
                view = None
                for group, tables in dataset.schema.groups.items():
                    if getattr(group, "value", "") != "views":
                        continue
                    for table_name in tables:
                        view = dataset.get_data(table_name, ids=frame_id)
                        if view is not None:
                            break
                    if view is not None:
                        break
                if view is None:
                    raise ValueError(f"Could not resolve view id '{frame_id}' for embedding.")
                views.append(view)
            view_type = type(views[0])
            if is_image(view_type) or is_sequence_frame(view_type):
                views = cast(list[Image], views)
                return super().compute_source_embeddings(self._open_views(views=views), *args, **kwargs)
            else:
                raise ValueError(f"View type {view_type} not supported for embedding.")

    return ViewEmbeddingFunction
