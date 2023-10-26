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

from pixano.data.dataset_info import DatasetInfo


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
            saved_info = DatasetInfo.parse_file(Path(temp_dir) / "db.json")

            self.assertTrue(isinstance(saved_info, DatasetInfo))
            self.assertEqual(self.info.id, saved_info.id)
            self.assertEqual(self.info.name, saved_info.name)
            self.assertEqual(self.info.description, saved_info.description)

    def test_dict(self):
        info_to_dict = self.info.dict()

        self.assertTrue(isinstance(info_to_dict, dict))
        self.assertEqual(self.info.id, info_to_dict["id"])
        self.assertEqual(self.info.name, info_to_dict["name"])
        self.assertEqual(self.info.description, info_to_dict["description"])

        info_from_dict = DatasetInfo(**info_to_dict)

        self.assertTrue(isinstance(info_from_dict, DatasetInfo))
        self.assertEqual(self.info.id, info_from_dict.id)
        self.assertEqual(self.info.name, info_from_dict.name)
        self.assertEqual(self.info.description, info_from_dict.description)
