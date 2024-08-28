# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from typing import cast

from pixano.datasets import DatasetItem
from pixano.features import Annotation, Embedding, Entity, Item, View

from .annotations import AnnotationModel
from .embeddings import EmbeddingModel
from .entities import EntityModel
from .items import ItemModel
from .views import ViewModel


class DatasetItemModel(DatasetItem):
    """DatasetItem model."""

    id: str
    item: ItemModel
    entities: dict[str, list[EntityModel] | EntityModel | None] = {}
    embeddings: dict[str, list[EmbeddingModel] | EmbeddingModel | None] = {}
    annotations: dict[str, list[AnnotationModel] | AnnotationModel | None] = {}
    views: dict[str, list[ViewModel] | ViewModel | None] = {}

    @classmethod
    def from_dataset_item(cls, dataset_item: DatasetItem) -> "DatasetItemModel":
        """Create a model from a dataset item."""
        raise NotImplementedError
        model_dict = {}
        for key, value in dataset_item.to_schemas_data().items():
            if value is None:
                model_dict[key] = None
            elif isinstance(value, Item):
                model_dict["item"] = ItemModel.from_row(value)
            elif isinstance(value, Annotation):
                model_dict["annotations"][key] = AnnotationModel.from_row(value)
            elif isinstance(value, Embedding):
                model_dict["embeddings"][key] = EmbeddingModel.from_row(value)
            elif isinstance(value, Entity):
                model_dict["entities"][key] = EntityModel.from_row(value)
            elif isinstance(value, View):
                model_dict["views"][key] = ViewModel.from_row(value)
            elif isinstance(value, list):
                if isinstance(value[0], Annotation):
                    value = cast(list[Annotation], value)
                    model_dict["annotations"][key] = AnnotationModel.from_rows(value)
                elif isinstance(value[0], Embedding):
                    value = cast(list[Embedding], value)
                    model_dict["embeddings"][key] = EmbeddingModel.from_rows(value)
                elif isinstance(value[0], Entity):
                    value = cast(list[Entity], value)
                    model_dict["entities"][key] = EntityModel.from_rows(value)
                elif isinstance(value[0], View):
                    value = cast(list[View], value)
                    model_dict["views"][key] = ViewModel.from_rows(value)
                else:
                    raise ValueError(f"Unknown type: {value}")
            else:
                raise ValueError(f"Unknown type: {value}")
        model_dict["id"] = dataset_item.id
        return cls.model_validate(model_dict)

    @classmethod
    def from_dataset_items(cls, dataset_items: list[DatasetItem]) -> list["DatasetItemModel"]:
        """Create a list of models from a list of dataset items."""
        return [cls.from_dataset_item(dataset_item) for dataset_item in dataset_items]

    def to_dataset_item(self) -> DatasetItem:
        """Create a dataset item from a model."""
        schema_dict = self.model_dump()

        item = schema_dict.pop("item")
        schema_dict.update(item)

        annotations = schema_dict.pop("annotations")
        embeddings = schema_dict.pop("embeddings")
        entities = schema_dict.pop("entities")
        views = schema_dict.pop("views")

        def _lose_first_level_dict(dict_: dict) -> None:
            for key, value in dict_:
                schema_dict[key] = value
            return

        _lose_first_level_dict(annotations)
        _lose_first_level_dict(embeddings)
        _lose_first_level_dict(entities)
        _lose_first_level_dict(views)

        return DatasetItem.model_validate(schema_dict)

    @staticmethod
    def to_dataset_items(models: list["DatasetItemModel"]) -> list[DatasetItem]:
        """Create a list of dataset items from a list of models."""
        return [model.to_dataset_item() for model in models]
