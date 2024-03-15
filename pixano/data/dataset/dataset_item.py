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

from pixano.core.types.registry import _TABLE_TYPE_REGISTRY
from pixano.data.dataset.dataset_schema import DatasetSchema


class DatasetItem(BaseModel):
    """DatasetItem."""

    id: str


def create_custom_dataset_item_class(schema: DatasetSchema) -> type[DatasetItem]:
    """Create a custom dataset item class based on the schema.

    Args:
        schema (DatasetSchema): The dataset schema

    Returns:
        type[DatasetItem]: The custom dataset item class
    """
    tables = {
        table: (_TABLE_TYPE_REGISTRY[table_type], None)
        for table_group in schema.schemas.keys()
        for table, table_type in schema.schemas[table_group].items()
    }

    CustomDatasetItem = create_model(
        "CustomDatasetItem",
        **tables,
        __base__=DatasetItem,
    )
    CustomDatasetItem.__doc__ = "CustomDatasetItem"
    return CustomDatasetItem
