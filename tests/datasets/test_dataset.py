# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from lancedb.table import LanceTable

from pixano.datasets import Dataset
from pixano.datasets.dataset_features_values import DatasetFeaturesValues
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema
from pixano.datasets.features.schemas.items.item import Item

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
        "ids,limit,offset,expected_output",
        [
            (
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
                ["0", "1"],
                None,
                0,
                [
                    {"id": "0", "metadata": "metadata_0", "split": "test"},
                    {"id": "1", "metadata": "metadata_1", "split": "train"},
                ],
            ),
        ],
    )
    def test_get_data(self, ids, limit, offset, expected_output, dataset: Dataset):
        data = dataset.get_data("item", ids=ids, limit=limit, offset=offset)
        assert isinstance(data, list) and all(isinstance(d, Item) for d in data)
        for d, e in zip(data, expected_output):
            assert d.model_dump() == e

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
                        "keypoint": None
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
                        "keypoint": None
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
                        "keypoint": None
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
                        "keypoint": None
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
                        "keypoint": None
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
                        "keypoint": None
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
                        "keypoint": None
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
                        "keypoint": None
                    },
                ],
            ),
        ],
    )
    def test_get_dataset_item(self, dataset: Dataset, ids, limit, offset, expected_output):
        print(dataset.get_data("entities", ids=None, limit=100, offset=0))
        dataset_items = dataset.get_dataset_items(ids=ids, limit=limit, offset=offset)
        assert isinstance(dataset_items, list) and all(isinstance(d, DatasetItem) for d in dataset_items)
        for item, expected_output in zip(dataset_items, expected_output):
            print(item)
            assert item.model_dump() == expected_output
