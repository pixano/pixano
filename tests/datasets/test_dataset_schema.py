# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import copy
import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema, SchemaRelation
from pixano.datasets.features.schemas import BBox, Embedding, Entity, Image, Item, SequenceFrame, Track
from pixano.datasets.features.schemas.base_schema import BaseSchema
from pixano.datasets.features.schemas.registry import register_schema
from pixano.datasets.features.schemas.schema_group import _SchemaGroup


@pytest.fixture
def CustomItem():
    class CustomItem(Item):
        categories: tuple[str, ...]
        other_categories: list[int]

    try:
        register_schema(CustomItem)
    except ValueError:
        pass
    return CustomItem


@pytest.fixture
def CustomItem2():
    class CustomItem(Item):
        categories: tuple[str, ...]
        other_categories: list[int]
        name: str
        index: int

    return CustomItem


@pytest.fixture
def CustomDatasetItem():
    class CustomDatasetItem(DatasetItem):
        categories: tuple[str, ...]
        other_categories: list[int]
        image: Image
        entity: Entity
        bbox: list[BBox]
        name: str
        index: int

    return CustomDatasetItem


@pytest.fixture
def dataset_schema_1(CustomItem):
    return DatasetSchema(
        schemas={
            "item": CustomItem,
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


class TestDatasetSchema:
    def test_init(self):
        # Test 1: valid schema
        schema = DatasetSchema(
            schemas={
                "item": Item,
                "image": Image,
                "sequence_frame": SequenceFrame,
                "entity": Entity,
                "track": Track,
                "bbox": BBox,
                "embedding": Embedding,
            },
            relations={
                "item": {
                    "image": SchemaRelation.ONE_TO_ONE,
                    "sequence_frame": SchemaRelation.MANY_TO_ONE,
                },
                "image": {
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_ONE,
                },
            },
        )
        assert schema._groups == {
            _SchemaGroup.ITEM: ["item"],
            _SchemaGroup.VIEW: ["image", "sequence_frame"],
            _SchemaGroup.ENTITY: ["entity", "track"],
            _SchemaGroup.ANNOTATION: ["bbox"],
            _SchemaGroup.EMBEDDING: ["embedding"],
        }

    # Test 2: invalid schema (invalid table type)
    class InvalidTable(BaseSchema):
        pass

    with pytest.raises(
        ValidationError,
        match="Invalid table type <class 'tests.datasets.test_dataset_schema.TestDatasetSchema.InvalidTable'>",
    ):
        schema = DatasetSchema(
            schemas={
                "item": Item,
                "image": Image,
                "sequence_frame": SequenceFrame,
                "entity": Entity,
                "track": Track,
                "bbox": BBox,
                "embedding": Embedding,
                "invalid_table": InvalidTable,
            },
            relations={
                "item": {
                    "image": SchemaRelation.ONE_TO_ONE,
                    "sequence_frame": SchemaRelation.MANY_TO_ONE,
                },
                "image": {
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_ONE,
                },
            },
        )

    # Test 3: invalid schema (invalid table in relations)
    with pytest.raises(ValidationError, match="Table invalid_table not found in schemas."):
        schema = DatasetSchema(
            schemas={
                "item": Item,
                "image": Image,
                "sequence_frame": SequenceFrame,
                "entity": Entity,
                "track": Track,
                "bbox": BBox,
                "embedding": Embedding,
            },
            relations={
                "item": {
                    "image": SchemaRelation.ONE_TO_ONE,
                    "sequence_frame": SchemaRelation.MANY_TO_ONE,
                },
                "image": {
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_ONE,
                    "invalid_table": SchemaRelation.ONE_TO_ONE,
                },
            },
        )

    # Test 4: invalid schema (name format)
    with pytest.raises(ValidationError, match="Table Image should be formatted correctly."):
        schema = DatasetSchema(
            schemas={
                "item": Item,
                "Image": Image,
                "sequence_frame": SequenceFrame,
                "entity": Entity,
                "track": Track,
                "bbox": BBox,
                "embedding": Embedding,
            },
            relations={
                "item": {
                    "image": SchemaRelation.ONE_TO_ONE,
                    "sequence_frame": SchemaRelation.MANY_TO_ONE,
                },
                "image": {
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_ONE,
                },
            },
        )

    # Test 5: invalid schema (item not found)
    with pytest.raises(ValidationError, match="DatasetSchema should contain an item schema."):
        schema = DatasetSchema(
            schemas={
                "image": Image,
                "sequence_frame": SequenceFrame,
                "entity": Entity,
                "track": Track,
                "bbox": BBox,
                "embedding": Embedding,
            },
            relations={
                "image": {
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_ONE,
                },
            },
        )

    # Test 6: invalid schema (two items)
    with pytest.raises(ValidationError, match="DatasetSchema should contain only one item schema."):
        schema = DatasetSchema(
            schemas={
                "item": Item,
                "item2": Item,
                "image": Image,
                "sequence_frame": SequenceFrame,
                "entity": Entity,
                "track": Track,
                "bbox": BBox,
                "embedding": Embedding,
            },
            relations={
                "item": {
                    "image": SchemaRelation.ONE_TO_ONE,
                    "sequence_frame": SchemaRelation.MANY_TO_ONE,
                },
                "image": {
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_ONE,
                },
            },
        )

    @pytest.mark.parametrize(
        "table_name, expected",
        [
            ("item", "item"),
            ("Image", "image"),
            ("SequenceFrame", "sequenceframe"),
            ("entity truc", "entity_truc"),
        ],
    )
    def test_format_table_name(self, table_name, expected):
        assert DatasetSchema.format_table_name(table_name) == expected

    def test_serialize(self, CustomItem, dataset_schema_1, json_dataset_schema_1):
        assert dataset_schema_1.serialize() == json_dataset_schema_1

    def test_to_json(self, CustomItem, dataset_schema_1, json_dataset_schema_1):
        json_fp = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        dataset_schema_1.to_json(json_fp)
        json_content = json.load(json_fp.open())
        assert json_content == json_dataset_schema_1

        dataset_schema_2 = copy.copy(dataset_schema_1)
        dataset_schema_2.schemas["item"] == Item  # Reset the custom item schema

        dataset_schema_2.to_json(json_fp)
        assert (
            json.load(json_fp.open()) == json_dataset_schema_1
        )  # The content should not have changed for the schema name

    def test_from_json(self, CustomItem, dataset_schema_1, json_dataset_schema_1):
        json_fp = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        json_fp.write_text(json.dumps(json_dataset_schema_1))

        schema = DatasetSchema.from_json(json_fp)
        assert schema.relations == dataset_schema_1.relations
        assert schema._groups == dataset_schema_1._groups
        assert set(schema.schemas.keys()) == set(dataset_schema_1.schemas.keys())
        assert all(schema.schemas[k].serialize() == dataset_schema_1.schemas[k].serialize() for k in schema.schemas)

    def test_from_dataset_item(self, CustomDatasetItem, CustomItem2):
        schema = DatasetSchema.from_dataset_item(CustomDatasetItem)
        assert set(schema.schemas.keys()) == {
            "item",
            "image",
            "entity",
            "bbox",
        }

        serialized_item = CustomItem2.serialize()
        serialized_item["schema"] = "Item"
        assert schema.schemas["item"].serialize() == serialized_item
        assert schema.schemas["image"].serialize() == Image.serialize()
        assert schema.schemas["entity"].serialize() == Entity.serialize()
        assert schema.schemas["bbox"].serialize() == BBox.serialize()

        assert schema.relations == {
            "item": {
                "image": SchemaRelation.ONE_TO_ONE,
                "entity": SchemaRelation.ONE_TO_ONE,
                "bbox": SchemaRelation.ONE_TO_MANY,
            },
            "image": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "entity": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "bbox": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
        }
        assert schema._groups == {
            _SchemaGroup.ITEM: ["item"],
            _SchemaGroup.VIEW: ["image"],
            _SchemaGroup.ENTITY: ["entity"],
            _SchemaGroup.ANNOTATION: ["bbox"],
            _SchemaGroup.EMBEDDING: [],
        }


class TestDatasetItem:
    def test_to_dataset_schema(self, CustomDatasetItem, CustomItem2):
        schema = CustomDatasetItem.to_dataset_schema()
        assert set(schema.schemas.keys()) == {
            "item",
            "image",
            "entity",
            "bbox",
        }

        assert set(schema.schemas.keys()) == {
            "item",
            "image",
            "entity",
            "bbox",
        }

        serialized_item = CustomItem2.serialize()
        serialized_item["schema"] = "Item"
        assert schema.schemas["item"].serialize() == serialized_item
        assert schema.schemas["image"].serialize() == Image.serialize()
        assert schema.schemas["entity"].serialize() == Entity.serialize()
        assert schema.schemas["bbox"].serialize() == BBox.serialize()

        assert schema.relations == {
            "item": {
                "image": SchemaRelation.ONE_TO_ONE,
                "entity": SchemaRelation.ONE_TO_ONE,
                "bbox": SchemaRelation.ONE_TO_MANY,
            },
            "image": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "entity": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "bbox": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
        }
        assert schema._groups == {
            _SchemaGroup.ITEM: ["item"],
            _SchemaGroup.VIEW: ["image"],
            _SchemaGroup.ENTITY: ["entity"],
            _SchemaGroup.ANNOTATION: ["bbox"],
            _SchemaGroup.EMBEDDING: [],
        }

    def test_from_dataset_schema(self, dataset_schema_1):
        type_dataset_item = DatasetItem.from_dataset_schema(dataset_schema_1)
        assert type_dataset_item.__name__ == "DatasetItem"
        assert set(type_dataset_item.model_fields.keys()) == {
            "id",
            "split",
            "categories",
            "other_categories",
            "image",
            "entity",
            "bbox",
        }

        # Default values
        dataset_item = type_dataset_item(
            id="id",
            split="default",
            categories=("cat1", "cat2"),
            other_categories=[1, 2, 3],
        )

        assert dataset_item.id == "id"
        assert dataset_item.split == "default"
        assert dataset_item.categories == ("cat1", "cat2")
        assert dataset_item.other_categories == [1, 2, 3]
        assert dataset_item.image is None
        assert dataset_item.entity is None
        assert dataset_item.bbox == []

        # With values
        dataset_item = type_dataset_item(
            id="id",
            split="default",
            categories=("cat1", "cat2"),
            other_categories=[1, 2, 3],
            image=Image(id="image_id", url="url", width=100, height=100, format="png"),
            entity=Entity(id="entity_id"),
            bbox=[BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5)],
        )

        assert dataset_item.id == "id"
        assert dataset_item.split == "default"
        assert dataset_item.categories == ("cat1", "cat2")
        assert dataset_item.image == Image(id="image_id", url="url", width=100, height=100, format="png")
        assert dataset_item.entity == Entity(id="entity_id")
        assert dataset_item.bbox == [
            BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5)
        ]

    def test_get_sub_dataset_item(self, CustomDatasetItem):
        sub_dataset_item = CustomDatasetItem.get_sub_dataset_item(["categories", "other_categories", "image", "bbox"])
        assert sub_dataset_item.__name__ == "CustomDatasetItem"
        assert set(sub_dataset_item.model_fields.keys()) == {
            "id",
            "split",
            "categories",
            "other_categories",
            "image",
            "bbox",
        }

        dataset_item = sub_dataset_item(
            id="id",
            split="default",
            categories=("cat1", "cat2"),
            other_categories=[1, 2, 3],
            image=Image(id="image_id", url="url", width=100, height=100, format="png"),
            bbox=[BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5)],
        )

        assert dataset_item.id == "id"
        assert dataset_item.split == "default"
        assert dataset_item.categories == ("cat1", "cat2")
        assert dataset_item.other_categories == [1, 2, 3]
        assert dataset_item.image == Image(id="image_id", url="url", width=100, height=100, format="png")
        assert dataset_item.bbox == [
            BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5)
        ]

    def test_to_schemas_data(self, CustomDatasetItem):
        dataset_schema = CustomDatasetItem.to_dataset_schema()
        my_custom_dataset_item = CustomDatasetItem(
            id="id",
            name="name",
            index=0,
            split="default",
            categories=("cat1", "cat2"),
            other_categories=[1, 2, 3],
            image=Image(id="image_id", url="url", width=100, height=100, format="png"),
            entity=Entity(id="entity_id"),
            bbox=[BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5)],
        )
        schemas_data = my_custom_dataset_item.to_schemas_data(dataset_schema)
        assert schemas_data == {
            "item": dataset_schema.schemas["item"](
                id="id",
                split="default",
                categories=("cat1", "cat2"),
                other_categories=[1, 2, 3],
                name="name",
                index=0,
            ),
            "image": Image(id="image_id", url="url", width=100, height=100, format="png"),
            "entity": Entity(id="entity_id"),
            "bbox": [BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5)],
        }
