# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pathlib import Path

import pytest
from lancedb.embeddings import get_registry
from lancedb.table import LanceTable

from pixano.datasets import Dataset
from pixano.datasets.dataset_features_values import DatasetFeaturesValues
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema, SchemaRelation
from pixano.features import Image, Item
from pixano.features.schemas.embeddings.embedding import ViewEmbedding
from pixano.features.types.schema_reference import ItemRef, ViewRef


class TestDataset:
    def test_dataset(self, dumb_dataset: Dataset, dataset_item_image_bboxes_keypoint: DatasetItem):
        assert isinstance(dumb_dataset, Dataset)
        assert isinstance(dumb_dataset.schema, DatasetSchema)
        assert isinstance(dumb_dataset.info, DatasetInfo)
        assert dumb_dataset.info == DatasetInfo(
            id=dumb_dataset.info.id, name="test", description="test", size="Unknown", num_elements=5, preview=""
        )
        assert dumb_dataset.schema.serialize() == dataset_item_image_bboxes_keypoint.to_dataset_schema().serialize()
        assert dumb_dataset.features_values == DatasetFeaturesValues()
        assert dumb_dataset.stats == []
        assert dumb_dataset.thumbnail == dumb_dataset.path / Dataset._THUMB_FILE
        assert dumb_dataset.num_rows == 5
        assert dumb_dataset.media_dir == dumb_dataset.path / "media"

    def test_create_table(self, dumb_dataset: Dataset):
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
        table = dumb_dataset.create_table("new_table", Image, SchemaRelation.ONE_TO_MANY, data=data)
        assert isinstance(table, LanceTable)
        assert "new_table" in dumb_dataset.schema.schemas
        assert issubclass(dumb_dataset.schema.schemas["new_table"], Image)
        assert dumb_dataset.schema.relations["item"]["new_table"] == SchemaRelation.MANY_TO_ONE
        assert "new_table" in dumb_dataset.dataset_item_model.model_fields

    def test_compute_embeddings(self, dumb_dataset: Dataset, dumb_embedding_function):
        registry = get_registry()
        registry._functions["test_compute_embeddings_dumb_embedding_function"] = dumb_embedding_function

        embeddings_schema: type[ViewEmbedding] = ViewEmbedding.create_schema(
            "test_compute_embeddings_dumb_embedding_function", "test_compute_embeddings_view_embedding", dumb_dataset
        )
        dumb_dataset.create_table(
            "test_compute_embeddings_view_embedding", embeddings_schema, SchemaRelation.ONE_TO_MANY
        )

        data = []
        views = dumb_dataset.get_data("image", limit=2)
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
        dumb_dataset.compute_view_embeddings("test_compute_embeddings_view_embedding", data)
        embeddings = dumb_dataset.get_data("test_compute_embeddings_view_embedding", limit=2)
        for i, embedding in enumerate(embeddings):
            assert embedding.vector == [1, 2, 3, 4, 5, 6, 7, 8]
            assert embedding.item_ref == ItemRef(id=views[i].item_ref.id, name=views[i].item_ref.name)
            assert embedding.view_ref == ViewRef(id=views[i].id, name="image")
            assert embedding.id == f"embedding_{i}"

    def test_open_table(self, dumb_dataset: Dataset):
        table = dumb_dataset.open_table("item")
        assert isinstance(table, LanceTable)

        with pytest.raises(ValueError, match="Table nonexistent not found in dataset"):
            dumb_dataset.open_table("nonexistent")

    def test_open_tables(self, dumb_dataset: Dataset):
        tables = dumb_dataset.open_tables()
        for table in tables.values():
            assert isinstance(table, LanceTable)
        assert set(tables.keys()) == set(dumb_dataset.schema.schemas.keys())

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
    def test_get_data(self, table_name, type, ids, item_ids, limit, skip, expected_output, dumb_dataset: Dataset):
        data = dumb_dataset.get_data(table_name=table_name, ids=ids, limit=limit, skip=skip, item_ids=item_ids)
        assert isinstance(data, list) and all(isinstance(d, type) for d in data)
        for d, e in zip(data, expected_output, strict=True):
            assert d.model_dump() == e
            assert d.dataset == dumb_dataset
            assert d.table_name == table_name

    def test_get_one_data(self, dumb_dataset: Dataset):
        data = dumb_dataset.get_data(table_name="item", ids="0")
        assert isinstance(data, Item)
        assert data.model_dump() == {"id": "0", "metadata": "metadata_0", "split": "test"}
        assert data.dataset == dumb_dataset

        data = dumb_dataset.get_data(table_name="item", ids="-1")
        assert data is None

    @pytest.mark.parametrize(
        "table_name,ids,item_ids,limit,skip,expected_error",
        [
            ("item", ["0"], ["0"], None, 0, "ids and item_ids cannot be set at the same time"),
            ("image", ["0"], ["0"], None, 0, "ids and item_ids cannot be set at the same time"),
            ("item", None, None, None, 0, "limit must be set if ids is None and item_ids is None"),
            ("item", ["0"], None, 1, 0, "ids or item_ids and limit cannot be set at the same time"),
            ("item", None, ["0"], 1, 0, "ids or item_ids and limit cannot be set at the same time"),
            ("item", [0], None, None, 0, "ids must be a list of strings"),
            ("item", 0, None, None, 0, "ids must be a list of strings"),
            ("image", None, [0], None, 0, "item_ids must be a list of strings"),
            ("image", None, 0, None, 0, "item_ids must be a list of strings"),
            ("item", None, None, 0, 0, "limit and skip must be positive integers"),
            ("item", None, None, 2, -1, "limit and skip must be positive integers"),
        ],
    )
    def test_get_data_error(self, table_name, ids, item_ids, limit, skip, expected_error, dumb_dataset: Dataset):
        with pytest.raises(ValueError, match=expected_error):
            dumb_dataset.get_data(table_name=table_name, ids=ids, limit=limit, skip=skip, item_ids=item_ids)

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
    def test_get_dataset_items(self, dumb_dataset: Dataset, ids, limit, skip, expected_output):
        dataset_items = dumb_dataset.get_dataset_items(ids=ids, limit=limit, skip=skip)
        assert isinstance(dataset_items, list) and all(isinstance(d, DatasetItem) for d in dataset_items)
        for item, expected_output in zip(dataset_items, expected_output):
            assert item.model_dump() == expected_output

    def test_get_one_dataset_item(self, dumb_dataset: Dataset):
        dataset_item = dumb_dataset.get_dataset_items(ids="0")
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

        dataset_item = dumb_dataset.get_dataset_items(ids="-1")
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
    def test_get_dataset_item_error(self, dumb_dataset: Dataset, ids, limit, skip, expected_error):
        with pytest.raises(ValueError, match=expected_error):
            dumb_dataset.get_dataset_items(ids=ids, limit=limit, skip=skip)

    def test_get_all_ids(self, dumb_dataset: Dataset):
        ids = dumb_dataset.get_all_ids()
        assert ids == ["0", "1", "2", "3", "4"]

        image_ids = dumb_dataset.get_all_ids(table_name="image")
        assert image_ids == ["image_0", "image_1", "image_2", "image_3", "image_4"]

    def test_add_data(self, dumb_dataset: Dataset):
        item = dumb_dataset.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()
        new_item.id = "new_item"

        assert dumb_dataset.get_data("item", ids=["new_item"]) == []

        added_data = dumb_dataset.add_data("item", [new_item])
        assert (
            dumb_dataset.get_data("item", ids=["new_item"])[0].model_dump()
            == new_item.model_dump()
            == added_data[0].model_dump()
        )

    def test_add_data_error(self, dumb_dataset: Dataset):
        item = dumb_dataset.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()

        data = [new_item, "0"]
        with pytest.raises(
            ValueError, match="All data must be instances of the table type <class 'pydantic.main.Item'>"
        ):
            dumb_dataset.add_data("item", data)

    def test_add_dataset_items(self, dumb_dataset: Dataset):
        item = dumb_dataset.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()
        new_item.id = "new_item"

        for table_name in dumb_dataset.schema.schemas.keys():
            if table_name == "item":
                continue
            field_schema = getattr(new_item, table_name)
            if isinstance(field_schema, list):
                for i, field in enumerate(field_schema):
                    setattr(field, "id", f"new_{table_name}_{i}")
                    setattr(field, "item_ref", {"id": "new_item", "name": "item"})
                    assert dumb_dataset.get_data(table_name, ids=[f"new_{table_name}_{i}"]) == []
            else:
                if field_schema is None:
                    continue
                setattr(field_schema, "id", f"new_{table_name}")
                setattr(field_schema, "item_ref", {"id": "new_item", "name": "item"})
                assert dumb_dataset.get_data(table_name, ids=[f"new_{table_name}"]) == []

        assert dumb_dataset.get_dataset_items(ids=["new_item"]) == []

        dataset_items = dumb_dataset.add_dataset_items([new_item])
        assert (
            dumb_dataset.get_dataset_items(ids=["new_item"])[0].model_dump()
            == new_item.model_dump()
            == dataset_items[0].model_dump()
        )

    def test_add_dataset_items_error(self, dumb_dataset: Dataset):
        item = dumb_dataset.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()

        data = [new_item, "0"]
        with pytest.raises(
            ValueError, match="All data must be instances of the dataset item type <class 'pydantic.main.DatasetItem'>"
        ):
            dumb_dataset.add_dataset_items(data)

    def test_delete_data(self, dumb_dataset: Dataset):
        dumb_dataset.get_data("item", ids=["0", "1"])[0]
        dumb_dataset.delete_data("item", ids=["0", "1"])
        assert dumb_dataset.get_data("item", ids=["0", "1"]) == []

    def test_delete_dataset_items(self, dumb_dataset: Dataset):
        dumb_dataset.get_dataset_items(ids=["0", "1"])
        dumb_dataset.delete_dataset_items(ids=["0", "1"])
        assert dumb_dataset.get_dataset_items(ids=["0", "1"]) == []

    def test_update_data(self, dumb_dataset: Dataset):
        item = dumb_dataset.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()
        new_item.metadata = "new_metadata"

        assert dumb_dataset.get_data("item", ids=["0"])[0].metadata == "metadata_0"
        updated_data = dumb_dataset.update_data("item", [new_item])
        assert (
            dumb_dataset.get_data("item", ids=["0"])[0].model_dump()
            == new_item.model_dump()
            == updated_data[0].model_dump()
        )

    def test_update_dataset_items(self, dumb_dataset: Dataset):
        item = dumb_dataset.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()
        new_item.metadata = "new_metadata"
        new_item.image.width = 200
        new_item.entities[0].id = "new_entity"
        new_item.bboxes[0].id = "new_bbox"

        updated_dataset_items = dumb_dataset.update_dataset_items([new_item])

        assert dumb_dataset.get_dataset_items(ids=["1"])[0] == new_item == updated_dataset_items[0]

    def test_find(self, dumb_dataset: Dataset):
        path = dumb_dataset.path.parent

        dumb_dataset_found = Dataset.find(dumb_dataset.info.id, path)
        assert dumb_dataset_found.info == dumb_dataset.info
        assert dumb_dataset_found.media_dir == dumb_dataset.media_dir

        dumb_dataset_found = Dataset.find(dumb_dataset.info.id, path, Path("/test/media"))
        assert dumb_dataset_found.info == dumb_dataset.info
        assert dumb_dataset_found.media_dir == Path("/test/media")

        with pytest.raises(FileNotFoundError, match=f"Dataset nonexistent not found in {path}"):
            Dataset.find("nonexistent", path)

    def test_resolve_ref(self, dumb_dataset: Dataset):
        item = dumb_dataset.get_data("item", ids=["0"])[0]
        item_ref = ItemRef(id="0", name="item")
        assert dumb_dataset.resolve_ref(item_ref) == item

        wrong_item_ref = ItemRef(id="", name="item")
        with pytest.raises(ValueError, match="Reference should have a name and an id."):
            dumb_dataset.resolve_ref(wrong_item_ref)
