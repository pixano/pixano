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

from pixano.data.dataset import Dataset
from pixano.data.dataset_info import DatasetInfo


class DatasetTestCase(unittest.TestCase):
    def setUp(self):
        self.path = Path("unit_testing/assets/vdp_dataset")
        self.dataset = Dataset(self.path)

    def test_info_property(self):
        self.assertTrue(isinstance(self.dataset.info, DatasetInfo))
        self.assertEqual(self.dataset.info.id, "vdp_dataset")

    def test_path_property(self):
        self.assertTrue(isinstance(self.dataset.path, Path))
        self.assertEqual(self.dataset.path, self.path)

    def test_media_dir_property(self):
        self.assertTrue(isinstance(self.dataset.media_dir, Path))
        self.assertEqual(self.dataset.media_dir, self.path / "media")

    def test_save_info(self):
        # Edit DatasetInfo
        self.dataset.info.id = "vdp_dataset_2"
        self.dataset.save_info()

        updated_info = DatasetInfo.parse_file(self.path / "db.json")
        self.assertEqual(updated_info.id, "vdp_dataset_2")

        # Revert DatasetInfo back to normal
        self.dataset.info.id = "vdp_dataset"
        self.dataset.save_info()

        updated_info = DatasetInfo.parse_file(self.path / "db.json")
        self.assertEqual(updated_info.id, "vdp_dataset")
