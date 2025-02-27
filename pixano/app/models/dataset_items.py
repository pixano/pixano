# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from pixano.datasets import Dataset, DatasetItem, DatasetSchema
from pixano.features import Annotation, Entity, Item, View
from pixano.features.schemas.base_schema import BaseSchema
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.schema_group import SchemaGroup
from pixano.utils.python import get_super_type_from_dict

from .annotations import AnnotationModel
from .base_schema import BaseSchemaModel
from .entities import EntityModel
from .items import ItemModel
from .table_info import TableInfo
from .views import ViewModel


class DatasetItemModel(BaseModel):
    """[DatasetItem][pixano.datasets.DatasetItem] model.

    It represents a dataset item with its associated entities, annotations and views.

    The mappings consist of the table name as key and the corresponding model or list of models as value.

    Attributes:
        id: The dataset item id.
        item: The item model.
        entities: The entities models mapping.
        annotations: The annotations models mapping.
        views: The views models mapping.
    """

    id: str
    item: ItemModel
    entities: dict[str, list[EntityModel] | EntityModel | None] = {}
    annotations: dict[str, list[AnnotationModel] | AnnotationModel | None] = {}
    views: dict[str, list[ViewModel] | ViewModel | None] = {}

    def model_dump(self, exclude_timestamps: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Dump the model to a dictionary.

        Args:
            exclude_timestamps: Exclude timestamps "created_at" and "updated_at" from the model dump. Useful for
                comparing models without timestamps.
            kwargs: Arguments for pydantic `BaseModel.model_dump()`.

        Returns:
            The model dump.
        """
        model_dump = super().model_dump(**kwargs)
        if exclude_timestamps:
            model_dump["item"].pop("created_at", None)
            model_dump["item"].pop("updated_at", None)
            for k in ["entities", "annotations", "views"]:
                for model in model_dump[k].values():
                    if model is None:
                        continue
                    elif isinstance(model, list):  # Only one level deep.
                        for item in model:
                            item.pop("created_at", None)
                            item.pop("updated_at", None)
                    else:
                        model.pop("created_at", None)
                        model.pop("updated_at", None)
        return model_dump

    @classmethod
    def from_dataset_item(cls, dataset_item: DatasetItem, dataset_schema: DatasetSchema) -> Self:
        """Create a model from a [DatasetItem][pixano.datasets.DatasetItem].

        Args:
            dataset_item: The dataset item to create the model from.
            dataset_schema: The schema of the dataset containing the dataset item.

        Returns:
            The created model.
        """

        def _row_or_rows_to_model_or_models(
            row_or_rows: BaseSchema | list[BaseSchema], name: str, group: SchemaGroup, model: type[BaseSchemaModel]
        ) -> BaseSchemaModel | list[BaseSchemaModel]:
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
    def from_dataset_items(cls, dataset_items: list[DatasetItem], dataset_schema: DatasetSchema) -> list[Self]:
        """Create a list of models from a list of [DatasetItem][pixano.datasets.DatasetItem]s.

        Args:
            dataset_items: The dataset items to create the models from.
            dataset_schema: The schema of the dataset containing the dataset item.

        Returns:
            The list of created models.
        """
        return [cls.from_dataset_item(dataset_item, dataset_schema) for dataset_item in dataset_items]

    def to_dataset_item(self, dataset: Dataset) -> DatasetItem:
        """Create a [DatasetItem][pixano.datasets.DatasetItem] from a model.

        Args:
            dataset: The dataset containing the model.

        Returns:
            The created dataset item.
        """
        schema_dict = {}

        item = self.item
        schema_dict.update(item.to_row(dataset).model_dump())

        for group in [self.annotations, self.entities, self.views]:
            for key, value in group.items():
                if isinstance(value, list):
                    schema_dict[key] = [v.to_row(dataset) for v in value]
                elif value is None:
                    schema_dict[key] = None
                else:
                    schema_dict[key] = value.to_row(dataset)

        return DatasetItem.from_dataset_schema(dataset.schema, exclude_embeddings=True).model_validate(schema_dict)

    @staticmethod
    def to_dataset_items(models: list["DatasetItemModel"], dataset: Dataset) -> list[DatasetItem]:
        """Create a list of [DatasetItem][pixano.datasets.DatasetItem]s from a list of models.

        Args:
            models: The models to create the dataset items from.
            dataset: The dataset containing the model.

        Returns:
            The list of created dataset items.
        """
        return [model.to_dataset_item(dataset) for model in models]
