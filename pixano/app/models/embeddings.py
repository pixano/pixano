# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator
from typing_extensions import TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import Embedding
from pixano.features.schemas.schema_group import SchemaGroup

from .base_schema import BaseSchemaModel


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

    def to_row(self, schema_type: type[T]) -> T:
        """Create an [Embedding][pixano.features.Embedding] from the model."""
        if not issubclass(schema_type, Embedding):
            raise ValueError(f"Schema type must be a subclass of {Embedding.__name__}.")
        return super().to_row(schema_type)
