# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator
from typing_extensions import TypeVar

from pixano.datasets import Dataset
from pixano.features import Embedding, SchemaGroup, is_embedding

from .base_schema import BaseSchemaModel
from .table_info import TableInfo


T = TypeVar("T", bound=Embedding)


class EmbeddingModel(BaseSchemaModel[Embedding]):
    """Model for the [Embedding][pixano.features.Embedding] schema."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "embedding_orange_cats",
                    "table_info": {"group": "embeddings", "name": "cat_embeddings", "base_schema": "ViewEmbedding"},
                    "data": {
                        "item_ref": {"name": "item", "id": "1"},
                        "view_ref": {"name": "image", "id": "orange_cats"},
                        "vector": [0.0, 1.0, 2.0, -1.0, -2.0, 0.0],
                        "shape": [6],
                    },
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def _validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.EMBEDDING.value:
            raise ValueError(f"Table info group must be {SchemaGroup.EMBEDDING.value}.")
        return value

    def to_row(self, dataset: Dataset) -> Embedding:
        """Create an [Embedding][pixano.features.Embedding] from the model."""
        if not is_embedding(dataset.schema.schemas[self.table_info.name]):
            raise ValueError(f"Schema type must be a subclass of {Embedding.__name__}.")
        return super().to_row(dataset)
