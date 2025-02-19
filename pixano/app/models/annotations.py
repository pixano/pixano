# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json

from pydantic import ConfigDict, field_validator
from typing_extensions import Self, TypeVar

from pixano.app.models.table_info import TableInfo
from pixano.features import Annotation
from pixano.features.schemas.schema_group import SchemaGroup

from .base_schema import BaseSchemaModel


T = TypeVar("T", bound=Annotation)


class AnnotationModel(BaseSchemaModel[Annotation]):
    """Model for the [Annotation][pixano.features.Annotation] schema."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "bbox_orange_cat_n1",
                    "table_info": {"group": "annotations", "name": "bboxes", "base_schema": "BBox"},
                    "data": {
                        "item_ref": {"name": "item", "id": "1"},
                        "view_ref": {"name": "image", "id": "orange_cats"},
                        "entity_ref": {
                            "name": "cats",
                            "id": "cat_n1",
                        },
                        "coords": [0, 0, 2, 2],
                        "format": "xywh",
                        "is_normalized": False,
                        "confidence": 0.8,
                        "inference_metadata": {},
                    },
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def _validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.ANNOTATION.value:
            raise ValueError(f"Table info group must be {SchemaGroup.ANNOTATION.value}.")
        return value

    def to_row(self, schema_type: type[T]) -> T:
        """Create an [Annotation][pixano.features.Annotation] from the model."""
        if not issubclass(schema_type, Annotation):
            raise ValueError(f"Schema type must be a subclass of {Annotation.__name__}.")
        row = super().to_row(schema_type)
        row.inference_metadata = json.dumps(self.data["inference_metadata"])
        return row

    @classmethod
    def from_row(cls, row: Annotation, table_info: TableInfo) -> Self:
        """Create an AnnotationModel from an [Annotation][pixano.features.Annotation].

        Args:
            row: The row to create the model from.
            table_info: The table info of the row.

        Returns:
            The created model.
        """
        annotation_model = BaseSchemaModel.from_row(row, table_info)
        annotation_model.data["inference_metadata"] = json.loads(row.inference_metadata)
        return cls.model_construct(**annotation_model.__dict__)  # Avoid validation and casting
