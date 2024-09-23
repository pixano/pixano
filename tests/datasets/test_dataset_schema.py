# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import copy
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema, SchemaRelation
from pixano.features.schemas import BBox, Embedding, Entity, Image, Item, SequenceFrame, Track
from pixano.features.schemas.base_schema import BaseSchema
from pixano.features.schemas.schema_group import SchemaGroup


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
                    "sequence_frame": SchemaRelation.ONE_TO_MANY,
                    "entity": SchemaRelation.ONE_TO_MANY,
                    "track": SchemaRelation.ONE_TO_MANY,
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_MANY,
                },
                "image": {
                    "item": SchemaRelation.ONE_TO_ONE,
                },
                "sequence_frame": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "entity": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "track": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "bbox": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "embedding": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
            },
        )
        assert schema.groups == {
            SchemaGroup.ITEM: {"item"},
            SchemaGroup.VIEW: {"image", "sequence_frame"},
            SchemaGroup.ENTITY: {"entity", "track"},
            SchemaGroup.ANNOTATION: {"bbox"},
            SchemaGroup.EMBEDDING: {"embedding"},
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
                    "sequence_frame": SchemaRelation.ONE_TO_MANY,
                    "entity": SchemaRelation.ONE_TO_MANY,
                    "track": SchemaRelation.ONE_TO_MANY,
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_MANY,
                },
                "image": {
                    "item": SchemaRelation.ONE_TO_ONE,
                },
                "sequence_frame": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "entity": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "track": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "bbox": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "embedding": {
                    "item": SchemaRelation.MANY_TO_ONE,
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
                    "sequence_frame": SchemaRelation.ONE_TO_MANY,
                    "entity": SchemaRelation.ONE_TO_MANY,
                    "track": SchemaRelation.ONE_TO_MANY,
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_MANY,
                    "invalid_table": SchemaRelation.ONE_TO_MANY,
                },
                "image": {
                    "item": SchemaRelation.ONE_TO_ONE,
                },
                "sequence_frame": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "entity": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "track": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "bbox": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "embedding": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "invalid_table": {
                    "item": SchemaRelation.MANY_TO_ONE,
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
                    "sequence_frame": SchemaRelation.ONE_TO_MANY,
                    "entity": SchemaRelation.ONE_TO_MANY,
                    "track": SchemaRelation.ONE_TO_MANY,
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_MANY,
                },
                "image": {
                    "item": SchemaRelation.ONE_TO_ONE,
                },
                "sequence_frame": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "entity": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "track": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "bbox": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "embedding": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
            },
        )

    # Test 5: invalid schema (item not found)
    with pytest.raises(ValidationError, match="Table item not found in schemas."):
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
                "item": {
                    "image": SchemaRelation.ONE_TO_ONE,
                    "sequence_frame": SchemaRelation.ONE_TO_MANY,
                    "entity": SchemaRelation.ONE_TO_MANY,
                    "track": SchemaRelation.ONE_TO_MANY,
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_MANY,
                },
                "image": {
                    "item": SchemaRelation.ONE_TO_ONE,
                },
                "sequence_frame": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "entity": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "track": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "bbox": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "embedding": {
                    "item": SchemaRelation.MANY_TO_ONE,
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
                    "sequence_frame": SchemaRelation.ONE_TO_MANY,
                    "entity": SchemaRelation.ONE_TO_MANY,
                    "track": SchemaRelation.ONE_TO_MANY,
                    "bbox": SchemaRelation.ONE_TO_MANY,
                    "embedding": SchemaRelation.ONE_TO_MANY,
                },
                "image": {
                    "item": SchemaRelation.ONE_TO_ONE,
                },
                "sequence_frame": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "entity": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "track": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "bbox": {
                    "item": SchemaRelation.MANY_TO_ONE,
                },
                "embedding": {
                    "item": SchemaRelation.MANY_TO_ONE,
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

    def test_serialize(
        self, dataset_schema_item_categories_image_bbox, json_dataset_schema_item_categories_image_bbox
    ):
        assert dataset_schema_item_categories_image_bbox.serialize() == json_dataset_schema_item_categories_image_bbox

    def test_to_json(self, dataset_schema_item_categories_image_bbox, json_dataset_schema_item_categories_image_bbox):
        json_fp = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        dataset_schema_item_categories_image_bbox.to_json(json_fp)
        json_content = json.load(json_fp.open())
        assert json_content == json_dataset_schema_item_categories_image_bbox

        dataset_schema_2 = copy.copy(dataset_schema_item_categories_image_bbox)
        dataset_schema_2.schemas["item"] == Item  # Reset the custom item schema

        dataset_schema_2.to_json(json_fp)
        assert (
            json.load(json_fp.open()) == json_dataset_schema_item_categories_image_bbox
        )  # The content should not have changed for the schema name

    def test_from_json(
        self, dataset_schema_item_categories_image_bbox, json_dataset_schema_item_categories_image_bbox
    ):
        json_fp = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        json_fp.write_text(json.dumps(json_dataset_schema_item_categories_image_bbox))

        schema = DatasetSchema.from_json(json_fp)
        assert schema.relations == dataset_schema_item_categories_image_bbox.relations
        assert schema.groups == dataset_schema_item_categories_image_bbox.groups
        assert set(schema.schemas.keys()) == set(dataset_schema_item_categories_image_bbox.schemas.keys())
        assert all(
            schema.schemas[k].serialize() == dataset_schema_item_categories_image_bbox.schemas[k].serialize()
            for k in schema.schemas
        )

    def test_from_dataset_item(self, dataset_item_bboxes_metadata, item_categories_name_index):
        schema = DatasetSchema.from_dataset_item(dataset_item_bboxes_metadata)
        assert set(schema.schemas.keys()) == {
            "item",
            "image",
            "entity",
            "bbox",
        }

        serialized_item = item_categories_name_index.serialize()
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
        assert schema.groups == {
            SchemaGroup.ITEM: {"item"},
            SchemaGroup.VIEW: {"image"},
            SchemaGroup.ENTITY: {"entity"},
            SchemaGroup.ANNOTATION: {"bbox"},
            SchemaGroup.EMBEDDING: set(),
        }

    @pytest.mark.parametrize(
        "relation",
        [
            SchemaRelation.ONE_TO_ONE,
            SchemaRelation.ONE_TO_MANY,
            SchemaRelation.MANY_TO_ONE,
            SchemaRelation.MANY_TO_MANY,
        ],
    )
    def test_add_schema(self, dataset_schema_item_categories_image_bbox, relation):
        if relation == SchemaRelation.ONE_TO_ONE:
            item_relation = SchemaRelation.ONE_TO_ONE
        elif relation == SchemaRelation.ONE_TO_MANY:
            item_relation = SchemaRelation.MANY_TO_ONE
        elif relation == SchemaRelation.MANY_TO_ONE:
            item_relation = SchemaRelation.ONE_TO_MANY
        else:
            item_relation = SchemaRelation.MANY_TO_MANY
        schema = dataset_schema_item_categories_image_bbox.add_schema("new_table", Image, relation)
        assert schema.schemas["new_table"] == Image
        assert schema.relations["new_table"] == {"item": relation}
        assert set(schema.groups[SchemaGroup.VIEW]) == {"image", "new_table"}
        assert schema.relations["item"]["new_table"] == item_relation

    def test_add_error(self, dataset_schema_item_categories_image_bbox):
        with pytest.raises(ValueError, match="Table image already exists in the schemas."):
            dataset_schema_item_categories_image_bbox.add_schema("image", Image, SchemaRelation.ONE_TO_ONE)

        with pytest.raises(ValueError, match="Schema <class 'str'> should be a subclass of BaseSchema."):
            dataset_schema_item_categories_image_bbox.add_schema("new_table", str, SchemaRelation.ONE_TO_ONE)

        with pytest.raises(ValueError, match="Invalid relation 1."):
            dataset_schema_item_categories_image_bbox.add_schema("new_table", Image, 1)


class TestDatasetItem:
    def test_to_dataset_schema(self, dataset_item_bboxes_metadata, item_categories_name_index):
        schema = dataset_item_bboxes_metadata.to_dataset_schema()
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

        serialized_item = item_categories_name_index.serialize()
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
        assert schema.groups == {
            SchemaGroup.ITEM: {"item"},
            SchemaGroup.VIEW: {"image"},
            SchemaGroup.ENTITY: {"entity"},
            SchemaGroup.ANNOTATION: {"bbox"},
            SchemaGroup.EMBEDDING: set(),
        }

    def test_from_dataset_schema(self, dataset_schema_item_categories_image_bbox):
        type_dataset_item = DatasetItem.from_dataset_schema(dataset_schema_item_categories_image_bbox)
        assert type_dataset_item.__name__ == "DatasetItem"
        assert set(type_dataset_item.model_fields.keys()) == {
            "id",
            "split",
            "categories",
            "other_categories",
            "image",
            "entity",
            "bbox",
            "created_at",
            "updated_at",
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
        assert dataset_item.image.model_dump(exclude_timestamps=True) == Image(
            id="image_id", url="url", width=100, height=100, format="png"
        ).model_dump(exclude_timestamps=True)
        assert dataset_item.entity.model_dump(exclude_timestamps=True) == Entity(id="entity_id").model_dump(
            exclude_timestamps=True
        )
        assert [dataset_item.bbox[0].model_dump(exclude_timestamps=True)] == [
            BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5).model_dump(
                exclude_timestamps=True
            )
        ]

    def test_from_dataset_schema_exclude_embeddings(
        self, dataset_schema_item_categories_name_index_image_bbox_embedding
    ):
        # Test with embeddings
        type_dataset_item = DatasetItem.from_dataset_schema(
            dataset_schema_item_categories_name_index_image_bbox_embedding, exclude_embeddings=False
        )
        assert set(type_dataset_item.model_fields.keys()) == {
            "embeddings",
            "bbox",
            "entity",
            "other_categories",
            "split",
            "image",
            "categories",
            "index",
            "name",
            "id",
            "created_at",
            "updated_at",
        }

        # Test without embeddings
        type_dataset_item = DatasetItem.from_dataset_schema(
            dataset_schema_item_categories_name_index_image_bbox_embedding, exclude_embeddings=True
        )
        assert set(type_dataset_item.model_fields.keys()) == {
            "entity",
            "bbox",
            "other_categories",
            "split",
            "image",
            "categories",
            "index",
            "name",
            "id",
            "created_at",
            "updated_at",
        }

    def test_get_sub_dataset_item(self, dataset_item_bboxes_metadata):
        sub_dataset_item = dataset_item_bboxes_metadata.get_sub_dataset_item(
            ["categories", "other_categories", "image", "bbox"]
        )
        assert sub_dataset_item.__name__ == "CustomDatasetItem"
        assert set(sub_dataset_item.model_fields.keys()) == {
            "id",
            "split",
            "categories",
            "other_categories",
            "image",
            "bbox",
            "created_at",
            "updated_at",
        }

        dataset_item = sub_dataset_item(
            id="id",
            split="default",
            categories=("cat1", "cat2"),
            other_categories=[1, 2, 3],
            image=Image(
                id="image_id",
                url="url",
                width=100,
                height=100,
                format="png",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            bbox=[
                BBox(
                    id="bbox_id",
                    coords=[0, 0, 1, 1],
                    format="xywh",
                    is_normalized=False,
                    confidence=0.5,
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
            ],
        )

        assert dataset_item.id == "id"
        assert dataset_item.split == "default"
        assert dataset_item.categories == ("cat1", "cat2")
        assert dataset_item.other_categories == [1, 2, 3]
        assert dataset_item.image == Image(
            id="image_id",
            url="url",
            width=100,
            height=100,
            format="png",
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        assert dataset_item.bbox == [
            BBox(
                id="bbox_id",
                coords=[0, 0, 1, 1],
                format="xywh",
                is_normalized=False,
                confidence=0.5,
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )
        ]

    def test_to_schemas_data(self, dataset_item_bboxes_metadata):
        dataset_schema = dataset_item_bboxes_metadata.to_dataset_schema()
        my_custom_dataset_item = dataset_item_bboxes_metadata(
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
        expected_schemas_data = {
            "item": dataset_schema.schemas["item"](
                id="id",
                split="default",
                categories=("cat1", "cat2"),
                other_categories=[1, 2, 3],
                name="name",
                index=0,
            ).model_dump(exclude_timestamps=True),
            "image": Image(id="image_id", url="url", width=100, height=100, format="png").model_dump(
                exclude_timestamps=True
            ),
            "entity": Entity(id="entity_id").model_dump(exclude_timestamps=True),
            "bbox": [
                BBox(id="bbox_id", coords=[0, 0, 1, 1], format="xywh", is_normalized=False, confidence=0.5).model_dump(
                    exclude_timestamps=True
                )
            ],
        }
        for key, value in schemas_data.items():
            if isinstance(value, list):
                assert len(value) == len(expected_schemas_data[key])
                for v, expected_v in zip(value, expected_schemas_data[key]):
                    assert v.model_dump(exclude_timestamps=True) == expected_v
            else:
                assert value.model_dump(exclude_timestamps=True) == expected_schemas_data[key]
