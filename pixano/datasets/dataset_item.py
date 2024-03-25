# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from pydantic import BaseModel, create_model

from .dataset_schema import DatasetSchema, SchemaRelation
from .features.schemas.group import _SchemaGroup


class DatasetItem(BaseModel):
    """DatasetItem."""

    pass


def create_custom_dataset_item_class_from_dataset_schema(
    dataset_schema: DatasetSchema,
) -> type[DatasetItem]:
    """Create a custom dataset item class based on the schema.

    Args:
        dataset_schema (DatasetSchema): The dataset schema

    Returns:
        type[DatasetItem]: The custom dataset item class
    """
    item_type = dataset_schema.schemas[_SchemaGroup.ITEM.value]
    fields = {}

    for schema, relation in dataset_schema.relations[_SchemaGroup.ITEM.value].items():
        # Add default value in case an item does not have a specific view or object.
        if relation == SchemaRelation.ONE_TO_MANY:
            fields[schema] = (list[dataset_schema.schemas[schema]], [])
        else:
            fields[schema] = (dataset_schema.schemas[schema], None)

    for field_name, field in item_type.model_fields.items():
        # No default value as all items metadata should be retrieved.
        fields[field_name] = (field.annotation, ...)

    CustomDatasetItem = create_model(
        "CustomDatasetItem",
        **fields,
        __base__=DatasetItem,
    )
    CustomDatasetItem.__doc__ = "CustomDatasetItem"
    return CustomDatasetItem


def create_sub_dataset_item(
    dataset_item: DatasetItem,
    selected_fields: list[str],
) -> DatasetItem:
    """Create a sub dataset item based on the selected fields.

    Args:
        dataset_item (DatasetItem): The dataset item
        selected_fields (list[str]): The selected fields

    Returns:
        DatasetItem: The sub dataset item
    """
    kept_fields = {}
    for field_name, field in dataset_item.model_fields.items():
        if field_name in selected_fields or field_name == "id":
            kept_fields[field_name] = (field.annotation, field.default)

    CustomDatasetItem = create_model(
        "CustomDatasetItem",
        **kept_fields,
        __base__=DatasetItem,
    )

    return CustomDatasetItem
