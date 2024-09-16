# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import re
from pathlib import Path

import pytest
from lancedb.embeddings import get_registry
from lancedb.table import LanceTable

from pixano.datasets import Dataset
from pixano.datasets.dataset_features_values import DatasetFeaturesValues
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema, SchemaRelation
from pixano.features import BBox, Image, Item
from pixano.features.schemas.embeddings.embedding import ViewEmbedding
from pixano.features.types.schema_reference import ItemRef, ViewRef


class TestDataset:
    def test_dataset(self, dataset_image_bboxes_keypoint: Dataset, dataset_item_image_bboxes_keypoint: DatasetItem):
        assert isinstance(dataset_image_bboxes_keypoint, Dataset)
        assert isinstance(dataset_image_bboxes_keypoint.schema, DatasetSchema)
        assert isinstance(dataset_image_bboxes_keypoint.info, DatasetInfo)
        assert dataset_image_bboxes_keypoint.info == DatasetInfo(
            id="dataset_image_bboxes_keypoint",
            name="dataset_image_bboxes_keypoint",
            description="Description dataset_image_bboxes_keypoint.",
            size="Unknown",
            preview="",
        )
        assert (
            dataset_image_bboxes_keypoint.schema.serialize()
            == dataset_item_image_bboxes_keypoint.to_dataset_schema().serialize()
        )
        assert dataset_image_bboxes_keypoint.features_values == DatasetFeaturesValues()
        assert dataset_image_bboxes_keypoint.stats == []
        assert dataset_image_bboxes_keypoint.thumbnail == dataset_image_bboxes_keypoint.path / Dataset._THUMB_FILE
        assert dataset_image_bboxes_keypoint.num_rows == 5
        assert dataset_image_bboxes_keypoint.media_dir == dataset_image_bboxes_keypoint.path / "media"

    def test_create_table(self, dataset_image_bboxes_keypoint_copy: Dataset):
        data = [
            Image(
                id=f"new_image_{i}",
                url=f"new_image_{i}.jpg",
                width=100,
                height=100,
                format="jpg",
            )
            for i in range(5)
        ]
        table = dataset_image_bboxes_keypoint_copy.create_table(
            "new_table", Image, SchemaRelation.ONE_TO_MANY, data=data
        )
        assert isinstance(table, LanceTable)
        assert "new_table" in dataset_image_bboxes_keypoint_copy.schema.schemas
        assert issubclass(dataset_image_bboxes_keypoint_copy.schema.schemas["new_table"], Image)
        assert dataset_image_bboxes_keypoint_copy.schema.relations["item"]["new_table"] == SchemaRelation.MANY_TO_ONE
        assert "new_table" in dataset_image_bboxes_keypoint_copy.dataset_item_model.model_fields

    def test_compute_embeddings(self, dataset_image_bboxes_keypoint_copy: Dataset, dumb_embedding_function):
        registry = get_registry()
        registry._functions["test_compute_embeddings_dumb_embedding_function"] = dumb_embedding_function

        embeddings_schema: type[ViewEmbedding] = ViewEmbedding.create_schema(
            "test_compute_embeddings_dumb_embedding_function",
            "test_compute_embeddings_view_embedding",
            dataset_image_bboxes_keypoint_copy,
        )
        dataset_image_bboxes_keypoint_copy.create_table(
            "test_compute_embeddings_view_embedding", embeddings_schema, SchemaRelation.ONE_TO_MANY
        )

        data = []
        views = dataset_image_bboxes_keypoint_copy.get_data("image", limit=2)
        for i, view in enumerate(views):
            data.append(
                {
                    "id": f"embedding_{i}",
                    "item_ref": {
                        "id": view.item_ref.id,
                        "name": view.item_ref.name,
                    },
                    "view_ref": {
                        "id": view.id,
                        "name": "image",
                    },
                }
            )
        dataset_image_bboxes_keypoint_copy.compute_view_embeddings("test_compute_embeddings_view_embedding", data)
        embeddings = dataset_image_bboxes_keypoint_copy.get_data("test_compute_embeddings_view_embedding", limit=2)
        for i, embedding in enumerate(embeddings):
            assert embedding.vector == [1, 2, 3, 4, 5, 6, 7, 8]
            assert embedding.item_ref == ItemRef(id=views[i].item_ref.id, name=views[i].item_ref.name)
            assert embedding.view_ref == ViewRef(id=views[i].id, name="image")
            assert embedding.id == f"embedding_{i}"

    def test_open_table(self, dataset_image_bboxes_keypoint: Dataset):
        table = dataset_image_bboxes_keypoint.open_table("item")
        assert isinstance(table, LanceTable)

        with pytest.raises(ValueError, match="Table nonexistent not found in dataset"):
            dataset_image_bboxes_keypoint.open_table("nonexistent")

    def test_open_tables(self, dataset_image_bboxes_keypoint: Dataset):
        tables = dataset_image_bboxes_keypoint.open_tables()
        for table in tables.values():
            assert isinstance(table, LanceTable)
        assert set(tables.keys()) == set(dataset_image_bboxes_keypoint.schema.schemas.keys())

    @pytest.mark.parametrize(
        "table_name,type,ids,item_ids,limit,skip,expected_output",
        [
            (
                "item",
                Item,
                None,
                None,
                3,
                0,
                [
                    {"id": "0", "metadata": "metadata_0", "split": "test"},
                    {"id": "1", "metadata": "metadata_1", "split": "train"},
                    {"id": "2", "metadata": "metadata_2", "split": "test"},
                ],
            ),
            (
                "item",
                Item,
                None,
                None,
                3,
                2,
                [
                    {"id": "2", "metadata": "metadata_2", "split": "test"},
                    {"id": "3", "metadata": "metadata_3", "split": "train"},
                    {"id": "4", "metadata": "metadata_4", "split": "test"},
                ],
            ),
            (
                "item",
                Item,
                ["0", "1"],
                None,
                None,
                0,
                [
                    {"id": "0", "metadata": "metadata_0", "split": "test"},
                    {"id": "1", "metadata": "metadata_1", "split": "train"},
                ],
            ),
            (
                "item",
                Item,
                None,
                ["0", "1"],
                None,
                0,
                [
                    {"id": "0", "metadata": "metadata_0", "split": "test"},
                    {"id": "1", "metadata": "metadata_1", "split": "train"},
                ],
            ),
            (
                "image",
                Image,
                ["image_0", "image_1"],
                None,
                None,
                0,
                [
                    {
                        "id": "image_0",
                        "item_ref": {"id": "0", "name": "item"},
                        "parent_ref": {"id": "", "name": ""},
                        "url": "image_0.jpg",
                        "width": 100,
                        "height": 100,
                        "format": "jpg",
                    },
                    {
                        "id": "image_1",
                        "item_ref": {"id": "1", "name": "item"},
                        "parent_ref": {"id": "", "name": ""},
                        "url": "image_1.jpg",
                        "width": 100,
                        "height": 100,
                        "format": "jpg",
                    },
                ],
            ),
            (
                "image",
                Image,
                None,
                ["0", "1"],
                None,
                0,
                [
                    {
                        "id": "image_0",
                        "item_ref": {"id": "0", "name": "item"},
                        "parent_ref": {"id": "", "name": ""},
                        "url": "image_0.jpg",
                        "width": 100,
                        "height": 100,
                        "format": "jpg",
                    },
                    {
                        "id": "image_1",
                        "item_ref": {"id": "1", "name": "item"},
                        "parent_ref": {"id": "", "name": ""},
                        "url": "image_1.jpg",
                        "width": 100,
                        "height": 100,
                        "format": "jpg",
                    },
                ],
            ),
        ],
    )
    def test_get_data(
        self, table_name, type, ids, item_ids, limit, skip, expected_output, dataset_image_bboxes_keypoint: Dataset
    ):
        data = dataset_image_bboxes_keypoint.get_data(
            table_name=table_name, ids=ids, limit=limit, skip=skip, item_ids=item_ids
        )
        assert isinstance(data, list) and all(isinstance(d, type) for d in data)
        for d, e in zip(data, expected_output, strict=True):
            assert d.model_dump() == e
            assert d.dataset == dataset_image_bboxes_keypoint
            assert d.table_name == table_name

    @pytest.mark.parametrize(
        "table_name,type,ids,item_ids,limit,skip,expected_output",
        [
            (
                "bboxes_video",
                BBox,
                None,
                ["2"],
                3,
                1,
                [
                    {
                        "id": "bbox_2_0_0_1",
                        "item_ref": {"name": "item", "id": "2"},
                        "view_ref": {"name": "video", "id": "video_2_0"},
                        "entity_ref": {"name": "entities_video", "id": "entity_video_2_0_0"},
                        "coords": [1.0, 1.0, 25.0, 25.0],
                        "format": "xywh",
                        "is_normalized": False,
                        "confidence": 0.25,
                    },
                    {
                        "id": "bbox_2_1_0_0",
                        "item_ref": {"name": "item", "id": "2"},
                        "view_ref": {"name": "video", "id": "video_2_1"},
                        "entity_ref": {"name": "entities_video", "id": "entity_video_2_1_0"},
                        "coords": [0.0, 0.0, 0.0, 0.0],
                        "format": "xywh",
                        "is_normalized": False,
                        "confidence": 0.0,
                    },
                    {
                        "id": "bbox_2_1_0_1",
                        "item_ref": {"name": "item", "id": "2"},
                        "view_ref": {"name": "video", "id": "video_2_1"},
                        "entity_ref": {"name": "entities_video", "id": "entity_video_2_1_0"},
                        "coords": [1.0, 1.0, 25.0, 25.0],
                        "format": "xywh",
                        "is_normalized": False,
                        "confidence": 0.25,
                    },
                ],
            )
        ],
    )
    def test_get_data_item_ids_and_skip_limit(
        self,
        table_name,
        type,
        ids,
        item_ids,
        limit,
        skip,
        expected_output,
        dataset_multi_view_tracking_and_image: Dataset,
    ):
        data = dataset_multi_view_tracking_and_image.get_data(
            table_name=table_name, ids=ids, limit=limit, skip=skip, item_ids=item_ids
        )
        assert isinstance(data, list) and all(isinstance(d, type) for d in data)
        for d, e in zip(data, expected_output, strict=True):
            assert d.model_dump() == e
            assert d.dataset == dataset_multi_view_tracking_and_image
            assert d.table_name == table_name

    def test_get_one_data(self, dataset_image_bboxes_keypoint: Dataset):
        data = dataset_image_bboxes_keypoint.get_data(table_name="item", ids="0")
        assert isinstance(data, Item)
        assert data.model_dump() == {"id": "0", "metadata": "metadata_0", "split": "test"}
        assert data.dataset == dataset_image_bboxes_keypoint

        data = dataset_image_bboxes_keypoint.get_data(table_name="item", ids="-1")
        assert data is None

    @pytest.mark.parametrize(
        "table_name,ids,item_ids,limit,skip,expected_error",
        [
            ("item", ["0"], ["0"], None, 0, "ids and item_ids cannot be set at the same time"),
            ("image", ["0"], ["0"], None, 0, "ids and item_ids cannot be set at the same time"),
            ("item", None, None, None, 0, "limit must be set if ids is None and item_ids is None"),
            ("item", ["0"], None, 1, 0, "ids and limit cannot be set at the same time"),
            ("item", None, ["0"], 1, 0, "ids and limit cannot be set at the same time"),
            ("item", [0], None, None, 0, "ids must be a list of strings"),
            ("item", 0, None, None, 0, "ids must be a list of strings"),
            ("image", None, [0], None, 0, "item_ids must be a list of strings"),
            ("image", None, 0, None, 0, "item_ids must be a list of strings"),
            ("item", None, None, 0, 0, "limit and skip must be positive integers"),
            ("item", None, None, 2, -1, "limit and skip must be positive integers"),
        ],
    )
    def test_get_data_error(
        self, table_name, ids, item_ids, limit, skip, expected_error, dataset_image_bboxes_keypoint: Dataset
    ):
        with pytest.raises(ValueError, match=expected_error):
            dataset_image_bboxes_keypoint.get_data(
                table_name=table_name, ids=ids, limit=limit, skip=skip, item_ids=item_ids
            )

    @pytest.mark.parametrize(
        "ids,limit,skip,expected_output",
        [
            (
                None,
                3,
                0,
                [
                    {
                        "id": "0",
                        "metadata": "metadata_0",
                        "split": "test",
                        "image": {
                            "id": "image_0",
                            "item_ref": {"id": "0", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_0.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [],
                        "bboxes": [],
                        "keypoint": None,
                    },
                    {
                        "id": "1",
                        "metadata": "metadata_1",
                        "split": "train",
                        "image": {
                            "id": "image_1",
                            "item_ref": {"id": "1", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_1.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [
                            {
                                "id": "entity_1_0",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "parent_ref": {"id": "", "name": ""},
                            },
                            {
                                "id": "entity_1_1",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "parent_ref": {"id": "", "name": ""},
                            },
                        ],
                        "bboxes": [
                            {
                                "id": "bbox_1_0",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "entity_ref": {"id": "entity_1_0", "name": "entities"},
                                "coords": [0.0, 0.0, 100.0, 100.0],
                                "format": "xywh",
                                "is_normalized": False,
                                "confidence": 0.9,
                            },
                            {
                                "id": "bbox_1_1",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "entity_ref": {"id": "entity_1_1", "name": "entities"},
                                "coords": [0.0, 0.0, 100.0, 100.0],
                                "format": "xywh",
                                "is_normalized": False,
                                "confidence": 0.9,
                            },
                        ],
                        "keypoint": None,
                    },
                    {
                        "id": "2",
                        "metadata": "metadata_2",
                        "split": "test",
                        "image": {
                            "id": "image_2",
                            "item_ref": {"id": "2", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_2.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [],
                        "bboxes": [],
                        "keypoint": None,
                    },
                ],
            ),
            (
                None,
                3,
                2,
                [
                    {
                        "id": "2",
                        "metadata": "metadata_2",
                        "split": "test",
                        "image": {
                            "id": "image_2",
                            "item_ref": {"id": "2", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_2.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [],
                        "bboxes": [],
                        "keypoint": None,
                    },
                    {
                        "id": "3",
                        "metadata": "metadata_3",
                        "split": "train",
                        "image": {
                            "id": "image_3",
                            "item_ref": {"id": "3", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_3.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [
                            {
                                "id": "entity_3_0",
                                "item_ref": {"id": "3", "name": "item"},
                                "view_ref": {"id": "image_3", "name": "image"},
                                "parent_ref": {"id": "", "name": ""},
                            },
                            {
                                "id": "entity_3_1",
                                "item_ref": {"id": "3", "name": "item"},
                                "view_ref": {"id": "image_3", "name": "image"},
                                "parent_ref": {"id": "", "name": ""},
                            },
                        ],
                        "bboxes": [
                            {
                                "id": "bbox_3_0",
                                "item_ref": {"id": "3", "name": "item"},
                                "view_ref": {"id": "image_3", "name": "image"},
                                "entity_ref": {"id": "entity_3_0", "name": "entities"},
                                "coords": [0.0, 0.0, 100.0, 100.0],
                                "format": "xywh",
                                "is_normalized": False,
                                "confidence": 0.9,
                            },
                            {
                                "id": "bbox_3_1",
                                "item_ref": {"id": "3", "name": "item"},
                                "view_ref": {"id": "image_3", "name": "image"},
                                "entity_ref": {"id": "entity_3_1", "name": "entities"},
                                "coords": [0.0, 0.0, 100.0, 100.0],
                                "format": "xywh",
                                "is_normalized": False,
                                "confidence": 0.9,
                            },
                        ],
                        "keypoint": None,
                    },
                    {
                        "id": "4",
                        "metadata": "metadata_4",
                        "split": "test",
                        "image": {
                            "id": "image_4",
                            "item_ref": {"id": "4", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_4.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [],
                        "bboxes": [],
                        "keypoint": None,
                    },
                ],
            ),
            (
                ["0", "1"],
                None,
                0,
                [
                    {
                        "id": "0",
                        "metadata": "metadata_0",
                        "split": "test",
                        "image": {
                            "id": "image_0",
                            "item_ref": {"id": "0", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_0.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [],
                        "bboxes": [],
                        "keypoint": None,
                    },
                    {
                        "id": "1",
                        "metadata": "metadata_1",
                        "split": "train",
                        "image": {
                            "id": "image_1",
                            "item_ref": {"id": "1", "name": "item"},
                            "parent_ref": {"id": "", "name": ""},
                            "url": "image_1.jpg",
                            "width": 100,
                            "height": 100,
                            "format": "jpg",
                        },
                        "entities": [
                            {
                                "id": "entity_1_0",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "parent_ref": {"id": "", "name": ""},
                            },
                            {
                                "id": "entity_1_1",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "parent_ref": {"id": "", "name": ""},
                            },
                        ],
                        "bboxes": [
                            {
                                "id": "bbox_1_0",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "entity_ref": {"id": "entity_1_0", "name": "entities"},
                                "coords": [0.0, 0.0, 100.0, 100.0],
                                "format": "xywh",
                                "is_normalized": False,
                                "confidence": 0.9,
                            },
                            {
                                "id": "bbox_1_1",
                                "item_ref": {"id": "1", "name": "item"},
                                "view_ref": {"id": "image_1", "name": "image"},
                                "entity_ref": {"id": "entity_1_1", "name": "entities"},
                                "coords": [0.0, 0.0, 100.0, 100.0],
                                "format": "xywh",
                                "is_normalized": False,
                                "confidence": 0.9,
                            },
                        ],
                        "keypoint": None,
                    },
                ],
            ),
        ],
    )
    def test_get_dataset_items(self, dataset_image_bboxes_keypoint: Dataset, ids, limit, skip, expected_output):
        dataset_items = dataset_image_bboxes_keypoint.get_dataset_items(ids=ids, limit=limit, skip=skip)
        assert isinstance(dataset_items, list) and all(isinstance(d, DatasetItem) for d in dataset_items)
        for item, expected_output in zip(dataset_items, expected_output):
            assert item.model_dump() == expected_output

    def test_get_one_dataset_item(self, dataset_image_bboxes_keypoint: Dataset):
        dataset_item = dataset_image_bboxes_keypoint.get_dataset_items(ids="0")
        expected_output = {
            "id": "0",
            "metadata": "metadata_0",
            "split": "test",
            "image": {
                "id": "image_0",
                "item_ref": {"id": "0", "name": "item"},
                "parent_ref": {"id": "", "name": ""},
                "url": "image_0.jpg",
                "width": 100,
                "height": 100,
                "format": "jpg",
            },
            "entities": [],
            "bboxes": [],
            "keypoint": None,
        }
        assert isinstance(dataset_item, DatasetItem)
        assert dataset_item.model_dump() == expected_output

        dataset_item = dataset_image_bboxes_keypoint.get_dataset_items(ids="-1")
        assert dataset_item is None

    @pytest.mark.parametrize(
        "ids,limit,skip,expected_error",
        [
            (["0"], 1, 0, "ids and limit cannot be set at the same time"),
            (None, 1, -1, "limit and skip must be positive integers"),
            (None, 0, 1, "limit and skip must be positive integers"),
            (1, None, 0, "ids must be a list of strings"),
            ([0], None, 0, "ids must be a list of strings"),
            (None, None, 0, "limit must be set if ids is None"),
        ],
    )
    def test_get_dataset_item_error(self, dataset_image_bboxes_keypoint: Dataset, ids, limit, skip, expected_error):
        with pytest.raises(ValueError, match=expected_error):
            dataset_image_bboxes_keypoint.get_dataset_items(ids=ids, limit=limit, skip=skip)

    def test_get_all_ids(self, dataset_image_bboxes_keypoint: Dataset):
        ids = dataset_image_bboxes_keypoint.get_all_ids()
        assert ids == ["0", "1", "2", "3", "4"]

        image_ids = dataset_image_bboxes_keypoint.get_all_ids(table_name="image")
        assert image_ids == ["image_0", "image_1", "image_2", "image_3", "image_4"]

    def test_add_data(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()
        new_item.id = "new_item"

        assert dataset_image_bboxes_keypoint_copy.get_data("item", ids=["new_item"]) == []

        added_data = dataset_image_bboxes_keypoint_copy.add_data("item", [new_item])
        assert (
            dataset_image_bboxes_keypoint_copy.get_data("item", ids=["new_item"])[0].model_dump()
            == new_item.model_dump()
            == added_data[0].model_dump()
        )

    def test_add_data_error(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()

        data = [new_item, "0"]
        with pytest.raises(
            ValueError, match="All data must be instances of the table type <class 'pydantic.main.Item'>"
        ):
            dataset_image_bboxes_keypoint_copy.add_data("item", data)

        data = [new_item]
        with pytest.raises(ValueError, match=re.escape("IDs ['0'] already exist in the table item.")):
            dataset_image_bboxes_keypoint_copy.add_data("item", data)

        data = [new_item, new_item]
        with pytest.raises(ValueError, match="All data must have unique ids."):
            dataset_image_bboxes_keypoint_copy.add_data("item", data)

    def test_add_dataset_items(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()
        new_item.id = "new_item"

        for table_name in dataset_image_bboxes_keypoint_copy.schema.schemas.keys():
            if table_name == "item":
                continue
            field_schema = getattr(new_item, table_name)
            if isinstance(field_schema, list):
                for i, field in enumerate(field_schema):
                    setattr(field, "id", f"new_{table_name}_{i}")
                    setattr(field, "item_ref", {"id": "new_item", "name": "item"})
                    assert dataset_image_bboxes_keypoint_copy.get_data(table_name, ids=[f"new_{table_name}_{i}"]) == []
            else:
                if field_schema is None:
                    continue
                setattr(field_schema, "id", f"new_{table_name}")
                setattr(field_schema, "item_ref", {"id": "new_item", "name": "item"})
                assert dataset_image_bboxes_keypoint_copy.get_data(table_name, ids=[f"new_{table_name}"]) == []

        assert dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["new_item"]) == []

        dataset_items = dataset_image_bboxes_keypoint_copy.add_dataset_items([new_item])
        assert (
            dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["new_item"])[0].model_dump()
            == new_item.model_dump()
            == dataset_items[0].model_dump()
        )

    def test_add_dataset_items_error(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()

        data = [new_item, "0"]
        with pytest.raises(ValueError, match="All data must be instances of the same DatasetItem."):
            dataset_image_bboxes_keypoint_copy.add_dataset_items(data)

        data = [new_item]
        with pytest.raises(ValueError, match=re.escape("IDs ['image_1'] already exist in the table image.")):
            dataset_image_bboxes_keypoint_copy.add_dataset_items(data)

        data = [new_item, new_item]
        with pytest.raises(ValueError, match="All data must have unique ids."):
            dataset_image_bboxes_keypoint_copy.add_dataset_items(data)

    def test_delete_data(self, dataset_image_bboxes_keypoint_copy: Dataset):
        dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0", "1"])[0]
        ids_not_found = dataset_image_bboxes_keypoint_copy.delete_data("item", ids=["0", "1", "-1"])
        assert ids_not_found == ["-1"]
        assert dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0", "1"]) == []

    def test_delete_dataset_items(self, dataset_image_bboxes_keypoint_copy: Dataset):
        dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["0", "1"])
        ids_not_found = dataset_image_bboxes_keypoint_copy.delete_dataset_items(ids=["0", "1", "-1"])
        assert ids_not_found == ["-1"]
        assert dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["0", "1"]) == []

    def test_update_data(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0"])[0]
        updated_item = item.model_copy()
        updated_item.metadata = "new_metadata"

        assert item.metadata == "metadata_0"
        updated_data = dataset_image_bboxes_keypoint_copy.update_data("item", [updated_item])
        assert (
            dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0"])[0].model_dump()
            == updated_item.model_dump()
            == updated_data[0].model_dump()
        )

        added_item = item.model_copy()
        updated_item.metadata = "new_metadata_2"
        added_item.id = "new_item"
        updated_data, added_data = dataset_image_bboxes_keypoint_copy.update_data(
            "item", [updated_item, added_item], return_separately=True
        )
        assert len(updated_data) == 1
        assert len(added_data) == 1

        assert (
            dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0"])[0].model_dump()
            == updated_data[0].model_dump()
            == updated_item.model_dump()
        )
        assert added_item.model_dump() == added_data[0].model_dump()

    def test_update_data_error(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_data("item", ids=["0"])[0]
        updated_item = item.model_copy()
        updated_item.id = "1"

        with pytest.raises(ValueError, match="All data must have unique ids."):
            dataset_image_bboxes_keypoint_copy.update_data("item", [updated_item, updated_item])

        data = [updated_item, "0"]
        with pytest.raises(
            ValueError, match="All data must be instances of the table type <class 'pydantic.main.Item'>"
        ):
            dataset_image_bboxes_keypoint_copy.add_data("item", data)

    def test_update_dataset_items(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["1"])[0]
        updated_item = item.model_copy()
        updated_item.metadata = "new_metadata"
        updated_item.image.width = 200
        updated_item.entities[0].id = "new_entity"
        updated_item.bboxes[0].id = "new_bbox"

        updated_dataset_items = dataset_image_bboxes_keypoint_copy.update_dataset_items([updated_item])

        assert (
            dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["1"])[0]
            == updated_item
            == updated_dataset_items[0]
        )

        added_item = type(item).model_validate(item.model_dump())
        added_item.id = "new_item"
        added_item.image.id = "new_image"
        added_item.entities[0].id = "new_entity_1"
        added_item.entities[1].id = "new_entity_2"
        added_item.bboxes[0].id = "new_bbox_1"
        added_item.bboxes[1].id = "new_bbox_2"
        updated_item.metadata = "new_metadata_2"
        updated_dataset_items, added_dataset_items = dataset_image_bboxes_keypoint_copy.update_dataset_items(
            [updated_item, added_item], return_separately=True
        )
        assert len(updated_dataset_items) == 1
        assert len(added_dataset_items) == 1
        assert updated_dataset_items[0] == updated_item
        assert added_dataset_items[0] == added_item

    def test_update_dataset_items_error(self, dataset_image_bboxes_keypoint_copy: Dataset):
        item = dataset_image_bboxes_keypoint_copy.get_dataset_items(ids=["1"])[0]
        updated_item = item.model_copy()
        updated_item.id = "0"

        with pytest.raises(ValueError, match="All data must have unique ids."):
            dataset_image_bboxes_keypoint_copy.update_dataset_items([updated_item, updated_item])

        data = [updated_item, "0"]
        with pytest.raises(ValueError, match="All data must be instances of the same DatasetItem."):
            dataset_image_bboxes_keypoint_copy.update_dataset_items(data)

    def test_find(self, dataset_image_bboxes_keypoint_copy: Dataset):
        path = dataset_image_bboxes_keypoint_copy.path.parent

        dataset_image_bboxes_keypoint_copy_found = Dataset.find(dataset_image_bboxes_keypoint_copy.info.id, path)
        assert dataset_image_bboxes_keypoint_copy_found.info == dataset_image_bboxes_keypoint_copy.info
        assert dataset_image_bboxes_keypoint_copy_found.path == dataset_image_bboxes_keypoint_copy.path
        assert dataset_image_bboxes_keypoint_copy_found.media_dir == dataset_image_bboxes_keypoint_copy.media_dir

        dataset_image_bboxes_keypoint_copy_found = Dataset.find(
            dataset_image_bboxes_keypoint_copy.info.id, path, Path("/test/media")
        )
        assert dataset_image_bboxes_keypoint_copy_found.info == dataset_image_bboxes_keypoint_copy.info
        assert dataset_image_bboxes_keypoint_copy_found.media_dir == Path("/test/media")

        with pytest.raises(FileNotFoundError, match=f"Dataset nonexistent not found in {path}"):
            Dataset.find("nonexistent", path)

    def test_resolve_ref(self, dataset_image_bboxes_keypoint: Dataset):
        item = dataset_image_bboxes_keypoint.get_data("item", ids=["0"])[0]
        item_ref = ItemRef(id="0", name="item")
        assert dataset_image_bboxes_keypoint.resolve_ref(item_ref) == item

        wrong_item_ref = ItemRef(id="", name="item")
        with pytest.raises(ValueError, match="Reference should have a name and an id."):
            dataset_image_bboxes_keypoint.resolve_ref(wrong_item_ref)
