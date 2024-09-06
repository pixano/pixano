# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_schema import DatasetSchema, SchemaRelation
from pixano.features.schemas import BBox, Entity, Image
from pixano.features.schemas.annotations.compressed_rle import CompressedRLE
from pixano.features.schemas.annotations.keypoints import KeyPoints
from pixano.features.schemas.annotations.tracklet import Tracklet
from pixano.features.schemas.entities.track import Track


@pytest.fixture()
def dataset_schema_item_categories_image_bbox(item_categories):
    return DatasetSchema(
        schemas={
            "item": item_categories,
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
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "entity": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "bbox": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
        },
    )


@pytest.fixture()
def json_dataset_schema_item_categories_image_bbox():
    return {
        "schemas": {
            "item": {
                "schema": "ItemCategories",
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
                "item": "one_to_one",
            },
            "entity": {
                "item": "one_to_one",
            },
            "bbox": {
                "item": "many_to_one",
            },
        },
        "groups": {
            "item": ["item"],
            "views": ["image"],
            "embeddings": [],
            "entities": ["entity"],
            "annotations": ["bbox"],
        },
    }


@pytest.fixture()
def dataset_schema_item_categories_name_index_image_bbox_embedding(item_categories_name_index, embedding_8):
    return DatasetSchema(
        schemas={
            "item": item_categories_name_index,
            "image": Image,
            "entity": Entity,
            "bbox": BBox,
            "embeddings": embedding_8,
        },
        relations={
            "item": {
                "image": SchemaRelation.ONE_TO_ONE,
                "entity": SchemaRelation.ONE_TO_MANY,
                "embeddings": SchemaRelation.ONE_TO_MANY,
                "bbox": SchemaRelation.ONE_TO_MANY,
            },
            "image": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "entity": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "bbox": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "embeddings": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
        },
    )


@pytest.fixture()
def json_dataset_schema_item_categories_name_index_image_bbox_embedding():
    return {
        "relations": {
            "item": {
                "image": "one_to_one",
                "entity": "one_to_many",
                "embeddings": "one_to_many",
                "bbox": "one_to_many",
            },
            "image": {"item": "one_to_one"},
            "entity": {"item": "many_to_one"},
            "bbox": {"item": "many_to_one"},
            "embeddings": {"item": "many_to_one"},
        },
        "schemas": {
            "item": {
                "schema": "ItemCategoriesNameIndex",
                "base_schema": "Item",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "split": {"type": "str", "collection": False},
                    "categories": {"type": "str", "collection": True},
                    "other_categories": {"type": "int", "collection": True},
                    "name": {"type": "str", "collection": False},
                    "index": {"type": "int", "collection": False},
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
            "embeddings": {
                "schema": "Embedding8",
                "base_schema": "Embedding",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "vector": {"type": "FixedSizeList", "collection": False, "dim": 8, "value_type": "float"},
                },
            },
        },
        "groups": {
            "annotations": ["bbox"],
            "embeddings": ["embeddings"],
            "item": ["item"],
            "entities": ["entity"],
            "views": ["image"],
        },
    }


@pytest.fixture()
def dataset_schema_multi_view_tracking_and_image(
    item_categories, sequence_frame_category, bbox_difficult, entity_category, view_embedding_8
):
    return DatasetSchema(
        schemas={
            "item": item_categories,
            "video": sequence_frame_category,
            "image": Image,
            "entity_image": entity_category,
            "entities_video": Entity,
            "tracks": Track,
            "bbox_image": bbox_difficult,
            "mask_image": CompressedRLE,
            "keypoints_image": KeyPoints,
            "bboxes_video": BBox,
            "keypoints_video": KeyPoints,
            "tracklets": Tracklet,
            "image_embedding": view_embedding_8,
            "video_embeddings": view_embedding_8,
        },
        relations={
            "item": {
                "video": SchemaRelation.ONE_TO_MANY,
                "image": SchemaRelation.ONE_TO_ONE,
                "entity_image": SchemaRelation.ONE_TO_ONE,
                "entities_video": SchemaRelation.ONE_TO_MANY,
                "tracks": SchemaRelation.ONE_TO_MANY,
                "bbox_image": SchemaRelation.ONE_TO_ONE,
                "mask_image": SchemaRelation.ONE_TO_ONE,
                "keypoints_image": SchemaRelation.ONE_TO_MANY,
                "bboxes_video": SchemaRelation.ONE_TO_MANY,
                "keypoints_video": SchemaRelation.ONE_TO_MANY,
                "tracklets": SchemaRelation.ONE_TO_MANY,
                "image_embedding": SchemaRelation.ONE_TO_ONE,
                "video_embeddings": SchemaRelation.ONE_TO_MANY,
            },
            "video": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "image": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "entity_image": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "entities_video": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "tracks": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "bbox_image": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "mask_image": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "keypoints_image": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "bboxes_video": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "keypoints_video": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "tracklets": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
            "image_embedding": {
                "item": SchemaRelation.ONE_TO_ONE,
            },
            "video_embeddings": {
                "item": SchemaRelation.MANY_TO_ONE,
            },
        },
    )


@pytest.fixture()
def json_dataset_schema_multi_view_tracking_and_image():
    return {
        "relations": {
            "item": {
                "video": "one_to_many",
                "image": "one_to_one",
                "entity_image": "one_to_one",
                "entities_video": "one_to_many",
                "tracks": "one_to_many",
                "bbox_image": "one_to_one",
                "mask_image": "one_to_one",
                "keypoints_image": "one_to_many",
                "bboxes_video": "one_to_many",
                "keypoints_video": "one_to_many",
                "tracklets": "one_to_many",
                "image_embedding": "one_to_one",
                "video_embeddings": "one_to_many",
            },
            "video": {"item": "many_to_one"},
            "image": {"item": "one_to_one"},
            "entity_image": {"item": "one_to_one"},
            "entities_video": {"item": "many_to_one"},
            "tracks": {"item": "many_to_one"},
            "bbox_image": {"item": "one_to_one"},
            "mask_image": {"item": "one_to_one"},
            "keypoints_image": {"item": "many_to_one"},
            "bboxes_video": {"item": "many_to_one"},
            "keypoints_video": {"item": "many_to_one"},
            "tracklets": {"item": "many_to_one"},
            "image_embedding": {"item": "one_to_one"},
            "video_embeddings": {"item": "many_to_one"},
        },
        "schemas": {
            "item": {
                "schema": "ItemCategories",
                "base_schema": "Item",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "split": {"type": "str", "collection": False},
                    "categories": {"type": "str", "collection": True},
                    "other_categories": {"type": "int", "collection": True},
                },
            },
            "video": {
                "schema": "SequenceFrameCategory",
                "base_schema": "SequenceFrame",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "parent_ref": {"type": "ViewRef", "collection": False},
                    "url": {"type": "str", "collection": False},
                    "width": {"type": "int", "collection": False},
                    "height": {"type": "int", "collection": False},
                    "format": {"type": "str", "collection": False},
                    "timestamp": {"type": "float", "collection": False},
                    "frame_index": {"type": "int", "collection": False},
                    "category": {"type": "str", "collection": False},
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
            "entity_image": {
                "schema": "EntityCategory",
                "base_schema": "Entity",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "parent_ref": {"type": "EntityRef", "collection": False},
                    "category": {"type": "str", "collection": False},
                },
            },
            "entities_video": {
                "schema": "Entity",
                "base_schema": "Entity",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "parent_ref": {"type": "EntityRef", "collection": False},
                },
            },
            "tracks": {
                "schema": "Track",
                "base_schema": "Track",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "parent_ref": {"type": "EntityRef", "collection": False},
                    "name": {"type": "str", "collection": False},
                },
            },
            "bbox_image": {
                "schema": "BBoxDifficult",
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
                    "is_difficult": {"type": "bool", "collection": False},
                },
            },
            "mask_image": {
                "schema": "CompressedRLE",
                "base_schema": "CompressedRLE",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "entity_ref": {"type": "EntityRef", "collection": False},
                    "size": {"type": "int", "collection": True},
                    "counts": {"type": "bytes", "collection": False},
                },
            },
            "keypoints_image": {
                "schema": "KeyPoints",
                "base_schema": "KeyPoints",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "entity_ref": {"type": "EntityRef", "collection": False},
                    "template_id": {"type": "str", "collection": False},
                    "coords": {"type": "float", "collection": True},
                    "states": {"type": "str", "collection": True},
                },
            },
            "bboxes_video": {
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
            "keypoints_video": {
                "schema": "KeyPoints",
                "base_schema": "KeyPoints",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "entity_ref": {"type": "EntityRef", "collection": False},
                    "template_id": {"type": "str", "collection": False},
                    "coords": {"type": "float", "collection": True},
                    "states": {"type": "str", "collection": True},
                },
            },
            "tracklets": {
                "schema": "Tracklet",
                "base_schema": "Tracklet",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "view_ref": {"type": "ViewRef", "collection": False},
                    "entity_ref": {"type": "EntityRef", "collection": False},
                    "start_timestep": {"type": "int", "collection": False},
                    "end_timestep": {"type": "int", "collection": False},
                    "start_timestamp": {"type": "float", "collection": False},
                    "end_timestamp": {"type": "float", "collection": False},
                },
            },
            "image_embedding": {
                "schema": "ViewEmbedding8",
                "base_schema": "ViewEmbedding",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "vector": {"type": "FixedSizeList", "collection": False, "dim": 8, "value_type": "float"},
                    "view_ref": {"type": "ViewRef", "collection": False},
                },
            },
            "video_embeddings": {
                "schema": "ViewEmbedding8",
                "base_schema": "ViewEmbedding",
                "fields": {
                    "id": {"type": "str", "collection": False},
                    "item_ref": {"type": "ItemRef", "collection": False},
                    "vector": {"type": "FixedSizeList", "collection": False, "dim": 8, "value_type": "float"},
                    "view_ref": {"type": "ViewRef", "collection": False},
                },
            },
        },
        "groups": {
            "annotations": [
                "keypoints_video",
                "bbox_image",
                "bboxes_video",
                "mask_image",
                "tracklets",
                "keypoints_image",
            ],
            "embeddings": ["image_embedding", "video_embeddings"],
            "item": ["item"],
            "entities": ["entities_video", "entity_image", "tracks"],
            "views": ["video", "image"],
        },
    }
