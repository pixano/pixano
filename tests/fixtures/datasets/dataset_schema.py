# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_schema import DatasetSchema, SchemaRelation
from pixano.datasets.features.schemas import BBox, Entity, Image

from .features import item as fixture_item


custom_item_1 = fixture_item.custom_item_1


@pytest.fixture
def dataset_schema_1(custom_item_1):
    return DatasetSchema(
        schemas={
            "item": custom_item_1,
            "image": Image,
            "entity": Entity,
            "bbox": BBox,
        },
        relations={
            "item": {
                "image": SchemaRelation.ONE_TO_ONE,
                "entity": SchemaRelation.ONE_TO_ONE,
                "bbox": SchemaRelation.ONE_TO_MANY,
            },
            "image": {
                "bbox": SchemaRelation.ONE_TO_MANY,
            },
        },
    )


@pytest.fixture
def json_dataset_schema_1():
    return {
        "schemas": {
            "item": {
                "schema": "CustomItem",
                "base_schema": "Item",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "split": {"type": "str", "collection": False},
                    "categories": {"type": "str", "collection": True},
                    "other_categories": {"type": "int", "collection": True},
                },
            },
            "image": {
                "schema": "Image",
                "base_schema": "Image",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "parent_ref": {"type": "ViewRef", "collection": False},
                    "url": {"type": "str", "collection": False},
                    "width": {"type": "int", "collection": False},
                    "height": {"type": "int", "collection": False},
                    "format": {"type": "str", "collection": False},
                },
            },
            "entity": {
                "schema": "Entity",
                "base_schema": "Entity",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "parent_ref": {"type": "EntityRef", "collection": False},
                },
            },
            "bbox": {
                "schema": "BBox",
                "base_schema": "BBox",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "entity_ref": {"type": "EntityRef", "collection": False},
                    "coords": {"type": "float", "collection": True},
                    "format": {"type": "str", "collection": False},
                    "is_normalized": {"type": "bool", "collection": False},
                    "confidence": {"type": "float", "collection": False},
                },
            },
        },
        "relations": {
            "item": {
                "image": "one_to_one",
                "entity": "one_to_one",
                "bbox": "one_to_many",
            },
            "image": {
                "bbox": "one_to_many",
            },
        },
    }
