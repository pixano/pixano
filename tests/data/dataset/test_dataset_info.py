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

import tempfile
import unittest
from pathlib import Path

from pixano.data import DatasetInfo


class DatasetInfoTestCase(unittest.TestCase):
    def setUp(self):
        self.info = DatasetInfo(
            id="datasetid001",
            name="My dataset",
            description="Dataset from a great AI project",
        )

    def test_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.info.save(Path(temp_dir))
            saved_info = DatasetInfo.from_json(Path(temp_dir) / "db.json")

            self.assertIsInstance(saved_info, DatasetInfo)
            self.assertEqual(self.info.id, saved_info.id)
            self.assertEqual(self.info.name, saved_info.name)
            self.assertEqual(self.info.description, saved_info.description)

    def test_dict(self):
        info_to_dict = self.info.model_dump()

        self.assertIsInstance(info_to_dict, dict)
        self.assertEqual(self.info.id, info_to_dict["id"])
        self.assertEqual(self.info.name, info_to_dict["name"])
        self.assertEqual(self.info.description, info_to_dict["description"])

        info_from_dict = DatasetInfo(**info_to_dict)

        self.assertIsInstance(info_from_dict, DatasetInfo)
        self.assertEqual(self.info.id, info_from_dict.id)
        self.assertEqual(self.info.name, info_from_dict.name)
        self.assertEqual(self.info.description, info_from_dict.description)

    def test_load_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dir1 = Path(temp_dir) / "dir1"
            dir2 = Path(temp_dir) / "dir2"
            dir3 = Path(temp_dir) / "dir3"

            dir1.mkdir()
            dir2.mkdir()
            dir3.mkdir()

            self.info.save(dir1)
            self.info.save(dir2)
            self.info.save(dir3)

            saved_infos = DatasetInfo.load_directory(Path(temp_dir))

            self.assertIsInstance(saved_infos, list)
            self.assertEqual(len(saved_infos), 3)

            for info in saved_infos:
                self.assertIsInstance(info, DatasetInfo)
                self.assertEqual(info.id, self.info.id)
                self.assertEqual(info.name, self.info.name)
                self.assertEqual(info.description, self.info.description)
