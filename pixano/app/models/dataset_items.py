# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from typing import Any

from pixano.datasets import DatasetItem, DatasetSchema
from pixano.features import Annotation, Entity, Item, View
from pixano.features.schemas.base_schema import BaseSchema
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.schema_group import SchemaGroup
from pixano.utils.python import get_super_type_from_dict

from .annotations import AnnotationModel
from .base_schema import BaseModelSchema
from .entities import EntityModel
from .items import ItemModel
from .table_info import TableInfo
from .views import ViewModel


class DatasetItemModel(DatasetItem):
    """DatasetItem model."""

    id: str
    item: ItemModel
    entities: dict[str, list[EntityModel] | EntityModel | None] = {}
    annotations: dict[str, list[AnnotationModel] | AnnotationModel | None] = {}
    views: dict[str, list[ViewModel] | ViewModel | None] = {}

    @classmethod
    def from_dataset_item(cls, dataset_item: DatasetItem, dataset_schema: DatasetSchema) -> "DatasetItemModel":
        """Create a model from a dataset item."""

        def _row_or_rows_to_model_or_models(
            row_or_rows: BaseSchema | list[BaseSchema], name: str, group: SchemaGroup, model: type[BaseModelSchema]
        ) -> BaseModelSchema | list[BaseModelSchema]:
            base_schema = get_super_type_from_dict(
                type(row_or_rows[0]) if isinstance(row_or_rows, list) else type(row_or_rows), _PIXANO_SCHEMA_REGISTRY
            )
            if base_schema is None:
                raise ValueError(f"Unsupported schema type {type(row_or_rows)}")
            table_info = TableInfo(name=name, group=group.value, base_schema=base_schema.__name__)
            if isinstance(row_or_rows, list):
                return model.from_rows(row_or_rows, table_info=table_info)
            else:
                return model.from_row(row_or_rows, table_info=table_info)

        model_dict: dict[str, Any] = {
            "entities": {},
            "annotations": {},
            "views": {},
        }
        for key, value in dataset_item.to_schemas_data(dataset_schema).items():
            if value is None or value == []:
                if issubclass(dataset_schema.schemas[key], View):
                    model_dict["views"][key] = None if value is None else []
                elif issubclass(dataset_schema.schemas[key], Entity):
                    model_dict["entities"][key] = None if value is None else []
                elif issubclass(dataset_schema.schemas[key], Annotation):
                    model_dict["annotations"][key] = None if value is None else []
                else:
                    raise ValueError(f"Unsupported schema type {type(value)}")
            elif isinstance(value, Item) or isinstance(value, list) and isinstance(value[0], Item):
                model_dict[key] = _row_or_rows_to_model_or_models(value, key, SchemaGroup.ITEM, ItemModel)
            elif isinstance(value, Annotation) or isinstance(value, list) and isinstance(value[0], Annotation):
                model_dict["annotations"][key] = _row_or_rows_to_model_or_models(
                    value, key, SchemaGroup.ANNOTATION, AnnotationModel
                )
            elif isinstance(value, Entity) or isinstance(value, list) and isinstance(value[0], Entity):
                model_dict["entities"][key] = _row_or_rows_to_model_or_models(
                    value, key, SchemaGroup.ENTITY, EntityModel
                )
            elif isinstance(value, View) or isinstance(value, list) and isinstance(value[0], View):
                model_dict["views"][key] = _row_or_rows_to_model_or_models(value, key, SchemaGroup.VIEW, ViewModel)
            else:
                raise ValueError(f"Unsupported schema type {type(value)}")
        model_dict["id"] = dataset_item.id
        return cls.model_validate(model_dict)

    @classmethod
    def from_dataset_items(
        cls, dataset_items: list[DatasetItem], dataset_schema: DatasetSchema
    ) -> list["DatasetItemModel"]:
        """Create a list of models from a list of dataset items."""
        return [cls.from_dataset_item(dataset_item, dataset_schema) for dataset_item in dataset_items]

    def to_dataset_item(self, dataset_schema: DatasetSchema) -> DatasetItem:
        """Create a dataset item from a model."""
        schema_dict = {}

        item = self.item
        schema_dict.update(item.to_row(dataset_schema.schemas["item"]).model_dump())

        for group in [self.annotations, self.entities, self.views]:
            for key, value in group.items():
                schema = dataset_schema.schemas[key]
                if isinstance(value, list):
                    schema_dict[key] = [v.to_row(schema) for v in value]
                elif value is None:
                    schema_dict[key] = None
                else:
                    schema_dict[key] = value.to_row(schema)

        return DatasetItem.from_dataset_schema(dataset_schema, exclude_embeddings=True).model_validate(schema_dict)

    @staticmethod
    def to_dataset_items(models: list["DatasetItemModel"], dataset_schema: DatasetSchema) -> list[DatasetItem]:
        """Create a list of dataset items from a list of models."""
        return [model.to_dataset_item(dataset_schema) for model in models]
