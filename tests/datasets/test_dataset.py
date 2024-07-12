# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest
from lancedb.table import LanceTable

from pixano.datasets import Dataset
from pixano.datasets.dataset_features_values import DatasetFeaturesValues
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema
from pixano.datasets.features import Image, Item

from .builders.test_dataset_builder import builder, dataset_item, info


builder = builder
dataset_item = dataset_item
info = info


@pytest.fixture
def dataset(builder):
    return builder.build()


class TestDataset:
    def test_dataset(self, dataset: Dataset, dataset_item: DatasetItem):
        assert isinstance(dataset, Dataset)
        assert isinstance(dataset.schema, DatasetSchema)
        assert isinstance(dataset.info, DatasetInfo)
        assert dataset.info == DatasetInfo(
            id=dataset.info.id, name="test", description="test", size="Unknown", num_elements=5, preview=""
        )
        assert dataset.schema.serialize() == dataset_item.to_dataset_schema().serialize()
        assert dataset.features_values == DatasetFeaturesValues()
        assert dataset.stats == []
        assert dataset.thumbnail == dataset.path / Dataset.THUMB_FILE
        assert dataset.num_rows == 5
        assert dataset.media_dir == dataset.path / "media"

    def test_open_table(self, dataset: Dataset):
        table = dataset.open_table("item")
        assert isinstance(table, LanceTable)

        with pytest.raises(ValueError, match="Table nonexistent not found in dataset"):
            dataset.open_table("nonexistent")

    def test_open_tables(self, dataset: Dataset):
        tables = dataset.open_tables()
        for table in tables.values():
            assert isinstance(table, LanceTable)
        assert set(tables.keys()) == set(dataset.schema.schemas.keys())

    @pytest.mark.parametrize(
        "table_name,type,ids,item_ids,limit,offset,expected_output",
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
    def test_get_data(self, table_name, type, ids, item_ids, limit, offset, expected_output, dataset: Dataset):
        data = dataset.get_data(table_name=table_name, ids=ids, limit=limit, offset=offset, item_ids=item_ids)
        assert isinstance(data, list) and all(isinstance(d, type) for d in data)
        for d, e in zip(data, expected_output, strict=True):
            assert d.model_dump() == e

    @pytest.mark.parametrize(
        "table_name,ids,item_ids,limit,offset,expected_error",
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
            ("item", None, None, 0, 0, "limit and offset must be positive integers"),
            ("item", None, None, 2, -1, "limit and offset must be positive integers"),
        ],
    )
    def test_get_data_error(self, table_name, ids, item_ids, limit, offset, expected_error, dataset: Dataset):
        with pytest.raises(ValueError, match=expected_error):
            dataset.get_data(table_name=table_name, ids=ids, limit=limit, offset=offset, item_ids=item_ids)

    @pytest.mark.parametrize(
        "ids,limit,offset,expected_output",
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
    def test_get_dataset_items(self, dataset: Dataset, ids, limit, offset, expected_output):
        dataset_items = dataset.get_dataset_items(ids=ids, limit=limit, offset=offset)
        assert isinstance(dataset_items, list) and all(isinstance(d, DatasetItem) for d in dataset_items)
        for item, expected_output in zip(dataset_items, expected_output):
            assert item.model_dump() == expected_output

    @pytest.mark.parametrize(
        "ids,limit,offset,expected_error",
        [
            (["0"], 1, 0, "ids and limit cannot be set at the same time"),
            (None, 1, -1, "limit and offset must be positive integers"),
            (None, 0, 1, "limit and offset must be positive integers"),
            (1, None, 0, "ids must be a list of strings"),
            ([0], None, 0, "ids must be a list of strings"),
            (None, None, 0, "limit must be set if ids is None"),
        ],
    )
    def test_get_dataset_item_error(self, dataset: Dataset, ids, limit, offset, expected_error):
        with pytest.raises(ValueError, match=expected_error):
            dataset.get_dataset_items(ids=ids, limit=limit, offset=offset)

    def test_get_all_ids(self, dataset: Dataset):
        ids = dataset.get_all_ids()
        assert ids == ["0", "1", "2", "3", "4"]

        image_ids = dataset.get_all_ids(table_name="image")
        assert image_ids == ["image_0", "image_1", "image_2", "image_3", "image_4"]

    def test_add_data(self, dataset: Dataset):
        item = dataset.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()
        new_item.id = "new_item"

        assert dataset.get_data("item", ids=["new_item"]) == []

        dataset.add_data("item", [new_item])
        assert dataset.get_data("item", ids=["new_item"])[0].model_dump() == new_item.model_dump()

    def test_add_data_error(self, dataset: Dataset):
        item = dataset.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()

        data = [new_item, "0"]
        with pytest.raises(
            ValueError, match="All data must be instances of the table type <class 'pydantic.main.Item'>"
        ):
            dataset.add_data("item", data)

    def test_add_dataset_items(self, dataset: Dataset):
        item = dataset.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()
        new_item.id = "new_item"

        for table_name in dataset.schema.schemas.keys():
            if table_name == "item":
                continue
            field_schema = getattr(new_item, table_name)
            if isinstance(field_schema, list):
                for i, field in enumerate(field_schema):
                    setattr(field, "id", f"new_{table_name}_{i}")
                    setattr(field, "item_ref", {"id": "new_item", "name": "item"})
                    assert dataset.get_data(table_name, ids=[f"new_{table_name}_{i}"]) == []
            else:
                if field_schema is None:
                    continue
                setattr(field_schema, "id", f"new_{table_name}")
                setattr(field_schema, "item_ref", {"id": "new_item", "name": "item"})
                assert dataset.get_data(table_name, ids=[f"new_{table_name}"]) == []

        assert dataset.get_dataset_items(ids=["new_item"]) == []

        dataset.add_dataset_items([new_item])
        assert dataset.get_dataset_items(ids=["new_item"])[0].model_dump() == new_item.model_dump()

    def test_add_dataset_items_error(self, dataset: Dataset):
        item = dataset.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()

        data = [new_item, "0"]
        with pytest.raises(
            ValueError, match="All data must be instances of the dataset item type <class 'pydantic.main.DatasetItem'>"
        ):
            dataset.add_dataset_items(data)

    def test_delete_data(self, dataset: Dataset):
        dataset.get_data("item", ids=["0", "1"])[0]
        dataset.delete_data("item", ids=["0", "1"])
        assert dataset.get_data("item", ids=["0", "1"]) == []

    def test_delete_dataset_items(self, dataset: Dataset):
        dataset.get_dataset_items(ids=["0", "1"])
        dataset.delete_dataset_items(ids=["0", "1"])
        assert dataset.get_dataset_items(ids=["0", "1"]) == []

    def test_update_data(self, dataset: Dataset):
        item = dataset.get_data("item", ids=["0"])[0]
        new_item = item.model_copy()
        new_item.metadata = "new_metadata"

        assert dataset.get_data("item", ids=["0"])[0].metadata == "metadata_0"
        dataset.update_data("item", [new_item])
        assert dataset.get_data("item", ids=["0"])[0].metadata == "new_metadata"

    def test_update_dataset_items(self, dataset: Dataset):
        item = dataset.get_dataset_items(ids=["1"])[0]
        new_item = item.model_copy()
        new_item.metadata = "new_metadata"
        new_item.image.width = 200
        new_item.entities[0].id = "new_entity"
        new_item.bboxes[0].id = "new_bbox"

        dataset.update_dataset_items([new_item])

        assert dataset.get_dataset_items(ids=["1"])[0] == new_item
