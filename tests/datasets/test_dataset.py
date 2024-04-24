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


import unittest
from pathlib import Path

import lancedb
import pytest

from pixano.datasets import Dataset, DatasetInfo, DatasetItem
from pixano.datasets.features.schemas.group import _SchemaGroup
from pixano.datasets.features.schemas.image import Image
from pixano.datasets.features.schemas.item import Item


class DatasetTestCase(unittest.TestCase):
    """Dataset test case"""

    def setUp(self):
        """Tests setup"""

        self.library_dir = Path("tests/assets")
        self.dataset_dir = self.library_dir / "output4"
        self.dataset = Dataset(self.dataset_dir)

    def test_path(self):
        """Test Dataset path property"""

        self.assertIsInstance(self.dataset.path, Path)
        self.assertEqual(self.dataset.path, self.dataset_dir)

    def test_num_rows(self):
        """Test Dataset num_rows property"""

        self.assertIsInstance(self.dataset.num_rows, int)
        self.assertEqual(self.dataset.num_rows, 25)

    def test_info(self):
        """Test Dataset info property"""

        self.assertIsInstance(self.dataset.info, DatasetInfo)
        self.assertEqual(self.dataset.info.id, "output4")
        self.assertEqual(self.dataset.info.name, "output4")

    def test_open_tables(self):
        """Test Dataset open_tables method"""

        ds_tables = self.dataset.open_tables()

        self.assertIsInstance(ds_tables, dict)
        self.assertIsInstance(
            ds_tables["item"],
            lancedb.db.LanceTable,
        )
        self.assertIsInstance(
            ds_tables["image"],
            lancedb.db.LanceTable,
        )
        self.assertEqual(len(ds_tables["item"]), 25)
        self.assertEqual(len(ds_tables["image"]), 25)

    def test_open_table(self):
        """Test Dataset open_table method"""

        item_table = self.dataset.open_table("item")
        image_table = self.dataset.open_table("image")

        self.assertIsInstance(item_table, lancedb.db.LanceTable)
        self.assertEqual(len(item_table), 25)
        self.assertIsInstance(image_table, lancedb.db.LanceTable)
        self.assertEqual(len(image_table), 25)

    def test_read_items(self):
        """Test Dataset read_items method"""

        # get item uuid from original id
        items = self.dataset.read_items(
            [
                "5o2RzUiNpGXKfPyUKM9Jcf",
                "6oGSRxK5wG9ND8SBwZA3Pp",
                "Ag97T8wTHqFCUB8urKXzgY",
                "C3f4NyKFMsEJjec53s9dUy",
                "D4shmyEUXXrzFEQcQoByJh",
            ]
        )

        for item in items:
            self.assertIsInstance(item, DatasetItem)
            self.assertIsInstance(item.id, str)
            self.assertIsInstance(item.split, str)
            self.assertIsInstance(item.image, Image)

    def test_read_item(self):
        """Test Dataset read_item method"""

        # get item uuid from original id
        item = self.dataset.read_item("5o2RzUiNpGXKfPyUKM9Jcf")

        self.assertIsInstance(item, DatasetItem)
        self.assertEqual(item.id, "5o2RzUiNpGXKfPyUKM9Jcf")
        self.assertIsInstance(item.split, str)
        self.assertIsInstance(item.image, Image)

    def test_read_views(self):
        """Test Dataset read_views method"""

        # get item uuid from original id
        items = self.dataset.read_views(
            [
                "5o2RzUiNpGXKfPyUKM9Jcf",
                "6oGSRxK5wG9ND8SBwZA3Pp",
                "Ag97T8wTHqFCUB8urKXzgY",
                "C3f4NyKFMsEJjec53s9dUy",
                "D4shmyEUXXrzFEQcQoByJh",
            ]
        )

        for item in items:
            self.assertIsInstance(item, DatasetItem)
            self.assertIsInstance(item.id, str)
            self.assertIsInstance(item.image, Image)
            with pytest.raises(AttributeError):
                item.split

    def test_read_view(self):
        """Test Dataset read_view method"""

        # get view uuid from original id
        item = self.dataset.read_view("5o2RzUiNpGXKfPyUKM9Jcf")

        self.assertIsInstance(item, DatasetItem)
        self.assertEqual(item.id, "5o2RzUiNpGXKfPyUKM9Jcf")
        self.assertIsInstance(item.image, Image)
        with pytest.raises(AttributeError):
            item.split

    def test_get_items(self):
        """Test Dataset get_items method"""

        # get item uuid from original id
        items = self.dataset.get_items(0, 5)

        assert len(items) == 5

        for item in items:
            self.assertIsInstance(item, DatasetItem)
            self.assertIsInstance(item.id, str)
            self.assertIsInstance(item.split, str)
            self.assertIsInstance(item.image, Image)

    def test_get_item(self):
        """Test Dataset get_item method"""

        # get item uuid from original id
        item = self.dataset.get_item(0)

        self.assertIsInstance(item, DatasetItem)
        self.assertEqual(item.id, "5o2RzUiNpGXKfPyUKM9Jcf")
        self.assertIsInstance(item.split, str)
        self.assertIsInstance(item.image, Image)

    def test_get_views(self):
        """Test Dataset get_views method"""

        # get item uuid from original id
        items = self.dataset.get_views(0, 5)

        assert len(items) == 5

        for item in items:
            self.assertIsInstance(item, DatasetItem)
            self.assertIsInstance(item.id, str)
            self.assertIsInstance(item.image, Image)
            with pytest.raises(AttributeError):
                item.split

    def test_get_view(self):
        """Test Dataset get_view method"""

        # get item uuid from original id
        item = self.dataset.get_view(0)

        self.assertIsInstance(item, DatasetItem)
        self.assertEqual(item.id, "5o2RzUiNpGXKfPyUKM9Jcf")
        self.assertIsInstance(item.image, Image)
        with pytest.raises(AttributeError):
            item.split

    def test_find(self):
        """Test Dataset find method"""

        found_dataset = Dataset.find("output4", self.library_dir)

        self.assertIsInstance(found_dataset, Dataset)
        assert found_dataset.info.id == self.dataset.info.id
